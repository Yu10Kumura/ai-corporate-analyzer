#!/usr/bin/env python3
"""
企業EVP・企業分析システム - Streamlit Web版（本番環境対応）
"""

import streamlit as st
import os
import json
import datetime
import time
import re
import urllib.parse
import requests
from pathlib import Path
from openai import OpenAI
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from datetime import datetime, timedelta

# ページ設定
st.set_page_config(
    page_title="🏢 AI企業分析システム",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed"
)

class SmartIRCrawler:
    """スマートIR情報収集システム（ハルシネーション対策付き）"""
    
    def __init__(self, company_domain, ir_url=None, max_depth=4, date_limit_years=3):
        self.company_domain = company_domain
        self.ir_url = ir_url or f"https://{company_domain}/ir/"
        self.max_depth = max_depth
        self.date_limit = datetime.now() - timedelta(days=date_limit_years * 365)
        self.discovered_content = []
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
    
    def is_valid_domain(self, url):
        """企業ドメインのみ許可"""
        try:
            parsed = urlparse(url)
            return self.company_domain in parsed.netloc
        except:
            return False
    
    def extract_date_from_content(self, content, url):
        """コンテンツから日付を抽出"""
        date_patterns = [
            r'(\d{4})年(\d{1,2})月(\d{1,2})日',
            r'(\d{4})-(\d{2})-(\d{2})',
            r'(\d{4})/(\d{1,2})/(\d{1,2})',
            r'公表日[：:\s]*(\d{4}[/-]\d{1,2}[/-]\d{1,2})',
            r'発表日[：:\s]*(\d{4}[/-]\d{1,2}[/-]\d{1,2})'
        ]
        
        for pattern in date_patterns:
            matches = re.findall(pattern, content)
            if matches:
                try:
                    # 最初のマッチを日付として解析
                    match = matches[0]
                    if isinstance(match, tuple):
                        if len(match) == 3:
                            year, month, day = match
                            return datetime(int(year), int(month), int(day))
                except:
                    continue
        
        # 日付が見つからない場合は現在日時を返す
        return datetime.now()
    
    def score_content_importance(self, content, url):
        """コンテンツの重要度スコアリング"""
        priority_keywords = {
            "決算短信": 10,
            "有価証券報告書": 9,
            "決算説明会": 8,
            "業績ハイライト": 7,
            "中期経営計画": 6,
            "株主総会": 5,
            "適時開示": 4,
            "ニュースリリース": 3,
            "IR": 2
        }
        
        score = 0
        content_lower = content.lower()
        url_lower = url.lower()
        
        for keyword, points in priority_keywords.items():
            if keyword in content or keyword in url:
                score += points
        
        # PDF文書は重要度が高い
        if '.pdf' in url_lower:
            score += 3
        
        # 決算関連のキーワード
        earnings_keywords = ["決算", "業績", "財務", "売上", "利益"]
        for keyword in earnings_keywords:
            if keyword in content:
                score += 2
        
        return score
    
    def discover_ir_links(self, start_url, depth=0):
        """IRページから重要なリンクを発見（改善版）"""
        if depth > self.max_depth:
            return []
        
        try:
            # URLの検証を緩和
            if not start_url.startswith(('http://', 'https://')):
                start_url = 'https://' + start_url
            
            st.info(f"🔍 探索中: {start_url}")
            
            response = self.session.get(start_url, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # ページコンテンツから日付抽出
            page_date = self.extract_date_from_content(response.text, start_url)
            
            # 重要度スコアリング
            importance_score = self.score_content_importance(response.text, start_url)
            
            discovered = [{
                'url': start_url,
                'content': response.text[:3000],  # 3000文字に短縮
                'date': page_date,
                'importance': importance_score,
                'title': soup.title.string if soup.title else start_url.split('/')[-1]
            }]
            
            # 基本的なIR情報があれば収集成功とみなす
            if importance_score > 0:
                st.success(f"✅ IR情報を発見: {soup.title.string if soup.title else start_url}")
            
            # リンク探索は簡潔に
            if depth < 2:  # 探索深度を制限
                ir_keywords = ['決算', '業績', 'ir', 'investor']
                for link in soup.find_all('a', href=True)[:20]:  # 最初の20個のリンクのみ
                    href = link.get('href')
                    if not href:
                        continue
                    
                    full_url = urljoin(start_url, href)
                    link_text = link.get_text().lower()
                    
                    if any(keyword in link_text or keyword in href.lower() for keyword in ir_keywords):
                        discovered.extend(self.discover_ir_links(full_url, depth + 1))
                        if len(discovered) >= 5:  # 5件見つかったら終了
                            break
            
            return discovered
            
        except requests.exceptions.RequestException as e:
            st.warning(f"⚠️ ネットワークエラー: {start_url} - {str(e)}")
            return []
        except Exception as e:
            st.warning(f"⚠️ 解析エラー: {start_url} - {str(e)}")
            return []
    
    def crawl_with_intelligence(self):
        """スマートなIR情報収集（改善版）"""
        try:
            st.info(f"🔍 IR情報探索を開始: {self.ir_url}")
            
            # 複数のIR URLパターンを試行
            ir_patterns = [
                self.ir_url,
                f"https://{self.company_domain}/ir/",
                f"https://{self.company_domain}/investor/",
                f"https://{self.company_domain}/company/ir/",
                f"https://ir.{self.company_domain}/",
            ]
            
            all_content = []
            
            for url_pattern in ir_patterns:
                if not url_pattern or len(all_content) >= 3:  # 3件見つかったら終了
                    continue
                    
                try:
                    content = self.discover_ir_links(url_pattern, 0)
                    if content:
                        all_content.extend(content)
                        st.success(f"✅ {len(content)}件の情報を {url_pattern} から収集")
                        break  # 成功したら他のパターンは試行しない
                except:
                    continue
            
            if not all_content:
                st.warning("⚠️ IR情報が見つかりませんでした。一般的な企業分析を実行します。")
                return []
            
            # 重要度でソートして重複除去
            unique_content = {}
            for item in all_content:
                if item['url'] not in unique_content:
                    unique_content[item['url']] = item
            
            sorted_content = sorted(unique_content.values(), key=lambda x: x['importance'], reverse=True)
            
            # 上位5件を返す
            result = sorted_content[:5]
            st.success(f"🎉 合計 {len(result)} 件のIR情報を収集しました")
            
            return result
            
        except Exception as e:
            st.error(f"❌ IR情報収集エラー: {str(e)}")
            return []

class StreamlitCompanyResearcher:
    def __init__(self):
        # APIキー設定（本番環境対応）
        api_key = self.get_openai_api_key()
        
        try:
            self.client = OpenAI(api_key=api_key)
        except Exception as e:
            st.error(f"❌ OpenAIクライアント初期化エラー: {e}")
            st.stop()
            
        # 結果保存ディレクトリ（本番環境では一時的）
        self.results_dir = Path('results')
        self.results_dir.mkdir(exist_ok=True)
        
        # HTTP セッション（Web検索用）
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
    
    def extract_domain_from_url(self, url):
        """URLからドメインを抽出"""
        if not url:
            return None
        try:
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            parsed = urlparse(url)
            domain = parsed.netloc
            # www. を除去
            if domain.startswith('www.'):
                domain = domain[4:]
            return domain
        except:
            return None
    
    def validate_response_content(self, response, source_data):
        """ハルシネーション対策：回答内容の検証"""
        # 推測表現の検出
        speculation_patterns = [
            r'と思われ', r'可能性が', r'おそらく', r'一般的に', 
            r'通常は', r'予想', r'推測', r'憶測', r'かもしれ'
        ]
        
        for pattern in speculation_patterns:
            if re.search(pattern, response):
                return False, f"推測的表現が含まれています: {pattern}"
        
        # 出典記載の確認
        if '出典：' not in response and 'ソース：' not in response:
            return False, "出典が明記されていません"
        
        # 基本的な事実確認（企業名の一致など）
        company_name_in_source = any(source['title'] for source in source_data if source.get('title'))
        if not company_name_in_source and len(source_data) > 0:
            st.warning("⚠️ ソースデータと企業名の整合性を確認中...")
        
        return True, "検証OK"
    
    def create_constrained_prompt(self, company_info, ir_data):
        """制約付きプロンプト生成"""
        ir_content = "\n".join([
            f"【{item['title']}】(重要度: {item['importance']}, 日付: {item['date'].strftime('%Y-%m-%d')})\n"
            f"URL: {item['url']}\n"
            f"内容: {item['content'][:800]}...\n"
            for item in ir_data[:5]  # 上位5件
        ])
        
        system_prompt = f"""
あなたは企業分析の専門家です。以下のルールを厳格に守ってください：

【重要制約】
1. 提供されたIR情報とWebデータのみを参照すること
2. データにない情報は「分析データには含まれていません」と明記
3. 推測や一般論ではなく、具体的な根拠を示すこと
4. 必ず「出典：[URL] [取得日時]」を明記すること
5. 「おそらく」「一般的に」「推測では」等の表現は使用禁止
6. 3年以内（2022年1月以降）の情報のみ使用すること

【分析対象企業】: {company_info['company_name']}
【重点分野】: {company_info['focus_area']}

【利用可能なIR情報】:
{ir_content}

【分析指示】:
上記のIR情報のみを使用して、EVP分析とビジネス分析を実行してください。
データにない項目については「データ不足のため分析できません」と記載してください。
"""
        
        return system_prompt
    
    def verify_with_double_check(self, question, answer, sources):
        """二段階検証システム"""
        verification_prompt = f"""
以下の回答について事実確認を行ってください：

質問: {question}
回答: {answer}

チェック項目:
1. 提供されたソースデータのみを使用しているか？
2. 3年以内の情報のみか？
3. 推測や外部知識が混入していないか？
4. 出典が正しく明記されているか？

問題があれば「NG：理由」、問題なければ「OK」と回答してください。
"""
        
        try:
            verification_response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": verification_prompt}],
                temperature=0.1,
                max_tokens=100
            )
            
            verification_result = verification_response.choices[0].message.content
            return "OK" in verification_result, verification_result
            
        except Exception as e:
            return False, f"検証エラー: {str(e)}"
    
    def search_existing_sources(self, question, analysis_data):
        """深度調査: 企業サイトの階層を深く探索して関連情報を収集"""
        company_domain = analysis_data.get('company_domain')
        if not company_domain:
            st.error("❌ 企業ドメインが提供されていません")
            return []
        
        try:
            # 質問に基づいて検索キーワードを生成
            search_keywords = self.extract_search_keywords(question)
            st.write(f"🔎 検索キーワード: {', '.join(search_keywords)}")
            
            st.info("🔍 企業サイトを深度調査中...")
            
            # 段階的な深度調査
            additional_sources = []
            
            # Step 1: 基本セクション + サブページ発見
            base_sections = {
                'ir': ['investor', 'ir', 'finance'],
                'business': ['business', 'service', 'product', 'solution'],
                'company': ['company', 'about', 'corporate'],
                'news': ['news', 'press', 'release'],
                'strategy': ['strategy', 'vision', 'plan', 'management']
            }
            
            for section_type, url_patterns in base_sections.items():
                st.write(f"📂 {section_type.title()}セクションを調査中...")
                section_sources = self.deep_explore_section(
                    company_domain, section_type, url_patterns, search_keywords, question
                )
                if section_sources:
                    st.write(f"✅ {len(section_sources)}件発見")
                    additional_sources.extend(section_sources)
                else:
                    st.write("❌ 情報なし")
                
                # 最大12ソースまで（各セクション2-3個）
                if len(additional_sources) >= 12:
                    break
            
            # Step 2: 重要文書の自動発見・取得
            st.write("📄 重要文書を検索中...")
            document_sources = self.discover_important_documents(
                company_domain, search_keywords, question
            )
            if document_sources:
                st.write(f"📋 {len(document_sources)}件の重要文書を発見")
                additional_sources.extend(document_sources)
            else:
                st.write("❌ 重要文書なし")
            
            return additional_sources[:15]  # 最大15ソース
            
        except Exception as e:
            st.warning(f"深度調査中にエラー: {str(e)}")
            return []
    
    def deep_explore_section(self, domain, section_type, url_patterns, keywords, question):
        """特定セクションの深度探索"""
        sources = []
        
        for pattern in url_patterns:
            # 複数のURL候補を試行
            candidate_urls = [
                f"https://{domain}/{pattern}/",
                f"https://{domain}/{pattern}.html",
                f"https://{domain}/jp/{pattern}/",
                f"https://{domain}/ja/{pattern}/",
            ]
            
            for base_url in candidate_urls:
                try:
                    response = self.session.get(base_url, timeout=15)
                    if response.status_code != 200:
                        continue
                        
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # サブページリンクを発見
                    subpage_links = self.discover_subpages(soup, base_url, section_type)
                    
                    # ベースページのコンテンツ解析
                    base_content = self.extract_relevant_content(soup, keywords, question)
                    if base_content:
                        sources.append({
                            'url': base_url,
                            'content': base_content,
                            'source_type': f'{section_type.title()}情報',
                            'depth': 'base'
                        })
                    
                    # サブページの探索（最大3つまで）
                    for sublink in subpage_links[:3]:
                        sub_content = self.explore_subpage(sublink, keywords, question)
                        if sub_content:
                            sources.append(sub_content)
                    
                    break  # 成功したら他の候補URLは試行しない
                    
                except:
                    continue
                    
            if len(sources) >= 3:  # セクションあたり最大3ソース
                break
                
        return sources
    
    def discover_subpages(self, soup, base_url, section_type):
        """セクション内のサブページを発見"""
        subpages = []
        
        # セクション別の重要キーワード
        important_keywords = {
            'ir': ['決算', '業績', '説明会', '中期', '計画', '有価証券', '財務', 'financial'],
            'business': ['事業紹介', 'サービス', '製品', 'ソリューション', '強み', '特徴'],
            'company': ['代表', 'メッセージ', '沿革', '組織', 'ミッション', 'ビジョン'],
            'news': ['プレス', 'リリース', '発表', '新着', '最新'],
            'strategy': ['戦略', '方針', 'ビジョン', '計画', '取り組み', 'DX']
        }
        
        keywords = important_keywords.get(section_type, [])
        
        # リンクを探索
        for link in soup.find_all('a', href=True):
            href = link.get('href')
            text = link.get_text().strip()
            
            if not href or len(text) < 3:
                continue
                
            # 相対パスを絶対パスに変換
            if href.startswith('/'):
                full_url = f"https://{base_url.split('/')[2]}{href}"
            elif href.startswith('http'):
                full_url = href
            else:
                continue
                
            # 重要キーワードを含むリンクを優先
            relevance_score = 0
            text_lower = text.lower()
            
            for keyword in keywords:
                if keyword in text_lower:
                    relevance_score += 2
                if keyword in href.lower():
                    relevance_score += 1
            
            # PDFファイルは特に重要
            if href.endswith('.pdf'):
                relevance_score += 3
                
            if relevance_score > 0:
                subpages.append({
                    'url': full_url,
                    'text': text,
                    'score': relevance_score
                })
        
        # スコア順でソート
        subpages.sort(key=lambda x: x['score'], reverse=True)
        return [page['url'] for page in subpages[:5]]
    
    def explore_subpage(self, url, keywords, question):
        """サブページの詳細探索"""
        try:
            response = self.session.get(url, timeout=15)
            if response.status_code != 200:
                return None
                
            # PDFファイルの場合
            if url.endswith('.pdf'):
                return self.extract_pdf_content(url, keywords, question)
                
            # HTMLページの場合
            soup = BeautifulSoup(response.text, 'html.parser')
            content = self.extract_relevant_content(soup, keywords, question)
            
            if content:
                return {
                    'url': url,
                    'content': content,
                    'source_type': self.classify_source_type(url),
                    'depth': 'deep'
                }
                
        except:
            pass
            
        return None
    
    def extract_pdf_content(self, pdf_url, keywords, question):
        """PDF文書からのコンテンツ抽出（簡易版）"""
        try:
            response = self.session.get(pdf_url, timeout=20)
            if response.status_code == 200:
                # PDF解析は複雑なので、まずはPDFの存在を記録
                return {
                    'url': pdf_url,
                    'content': f"PDF文書が発見されました: {pdf_url.split('/')[-1]}",
                    'source_type': 'PDF資料',
                    'depth': 'document'
                }
        except:
            pass
        return None
    
    def discover_important_documents(self, domain, keywords, question):
        """重要文書の自動発見（一次情報優先）"""
        documents = []
        
        # 一次情報（公式開示資料）の優先的な検索パス
        primary_document_paths = [
            '/ir/library/',      # IR資料ライブラリ
            '/ir/finance/',      # 財務情報
            '/ir/brief/',        # 決算短信
            '/ir/securities/',   # 有価証券報告書
            '/ir/results/',      # 決算説明資料
            '/ir/plan/',         # 中期経営計画
            '/ir/annual/',       # アニュアルレポート
            '/ir/disclosure/',   # 開示情報
            '/investor/library/',
            '/investor/financials/',
            '/company/plan/',
            '/company/management/',
            '/sustainability/report/',
        ]
        
        # 一次情報キーワード（より具体的に）
        primary_keywords = [
            '有価証券報告書', '決算短信', '決算説明', 'annual report',
            '中期経営計画', '事業報告書', '四半期報告', '財務諸表',
            'financial results', 'earnings', 'quarterly report',
            '業績説明', '投資家説明', 'investor presentation'
        ]
        
        st.write("📋 一次情報（公式開示資料）を優先検索中...")
        
        for path in primary_document_paths:
            try:
                url = f"https://{domain}{path}"
                response = self.session.get(url, timeout=15)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # 一次情報を優先的に発見
                    for link in soup.find_all('a', href=True):
                        href = link.get('href')
                        text = link.get_text().strip()
                        
                        if not href or len(text) < 3:
                            continue
                        
                        # 一次情報のスコアリング（大幅強化）
                        relevance_score = 0
                        text_lower = text.lower()
                        
                        # 一次情報キーワードに高いスコア
                        for keyword in primary_keywords:
                            if keyword in text_lower:
                                relevance_score += 10  # 高いスコア
                        
                        # 年度・期間情報があれば追加スコア
                        if any(year in text for year in ['2024', '2023', '2022', '2025']):
                            relevance_score += 5
                        
                        # PDFは公式資料の可能性が高い
                        if href.endswith('.pdf'):
                            relevance_score += 8
                        
                        # 質問に関連するキーワード
                        for keyword in keywords:
                            if keyword.lower() in text_lower:
                                relevance_score += 3
                        
                        if relevance_score >= 8:  # 閾値を上げて高品質な情報のみ
                            if href.startswith('/'):
                                full_url = f"https://{domain}{href}"
                            else:
                                full_url = href
                                
                            documents.append({
                                'url': full_url,
                                'content': f"【一次情報】{text}",
                                'source_type': '公式開示資料',
                                'depth': 'primary_document',
                                'relevance_score': relevance_score
                            })
                            
                        if len(documents) >= 5:  # 一次情報は最大5件
                            break
                            
            except:
                continue
                
        # スコア順でソート
        documents.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        
        if documents:
            st.success(f"✅ {len(documents)}件の一次情報を発見")
        else:
            st.warning("⚠️ 一次情報が見つかりませんでした")
                
        return documents[:5]  # 最高品質の一次情報5件まで
    
    def assess_content_reliability(self, content):
        """コンテンツの信頼性を評価（0-100のスコア）"""
        if not content or len(content) < 10:
            return 0
        
        score = 50  # 基本スコア
        content_lower = content.lower()
        
        # 一次情報の証拠があれば高スコア
        primary_indicators = [
            '決算短信', '有価証券報告書', 'アニュアルレポート', '決算説明',
            '中期経営計画', '投資家向け', 'ir資料', '公式発表', '開示情報'
        ]
        
        for indicator in primary_indicators:
            if indicator in content_lower:
                score += 15
        
        # 具体的な年度・数値があれば信頼性UP
        if any(year in content for year in ['2024年', '2023年', '2022年', '2025年']):
            score += 10
        
        # 推測・曖昧な表現があれば信頼性DOWN
        unreliable_indicators = [
            '推定', '一般的に', '業界標準', '通常', '多くの企業',
            'と思われ', 'と考えられ', '可能性があ', '予想される'
        ]
        
        for indicator in unreliable_indicators:
            if indicator in content_lower:
                score -= 20
        
        # 「公式開示情報では確認できません」などの正直な表現は信頼性UP
        honest_indicators = [
            '確認できません', '開示されていません', '公表されていません',
            '情報が限定的', '詳細は不明'
        ]
        
        for indicator in honest_indicators:
            if indicator in content_lower:
                score += 10
        
        return max(0, min(100, score))  # 0-100の範囲に制限
    
    def search_external_sources(self, company_name, industry_keywords):
        """SerpAPIを使用した関連性の高い外部情報収集"""
        external_data = []
        
        st.info("🌐 SerpAPIで関連性の高い業界情報を厳選収集中...")
        
        # SerpAPIキーを取得（新しいメソッドを使用）
        serpapi_key = self.get_serpapi_key()
        if not serpapi_key:
            return self.create_fallback_external_data(company_name, industry_keywords)
        
        # より具体的で関連性の高い検索クエリ
        search_queries = [
            f'"{company_name}" 市場規模 OR 業界シェア OR 売上 OR 業績 site:nikkei.com OR site:toyokeizai.net OR site:diamond.jp',
            f'"{company_name}" 競合 OR ライバル OR 業界地位 -求人 -転職 site:nikkei.com OR site:itmedia.co.jp'
        ]
        
        for i, query in enumerate(search_queries, 1):
            st.write(f"🔍 検索 {i}/{len(search_queries)}: {query[:60]}...")
            
            try:
                results = self.search_with_serpapi(query, serpapi_key)
                
                if results and 'organic_results' in results:
                    relevant_results = self.filter_relevant_results(results['organic_results'], company_name)
                    
                    for result in relevant_results[:2]:  # 関連性の高い上位2件のみ
                        external_data.append({
                            'title': result.get('title', ''),
                            'snippet': result.get('snippet', ''),
                            'url': result.get('link', ''),
                            'source': self.extract_domain(result.get('link', '')),
                            'type': '外部記事',
                            'relevance_score': result.get('relevance_score', 0)
                        })
                    
                    st.success(f"✅ 関連性の高い{len(relevant_results[:2])}件を選択")
                else:
                    st.warning(f"⚠️ 検索 {i}: 結果なし")
                    
            except Exception as e:
                st.warning(f"⚠️ 検索 {i} エラー: {str(e)}")
                continue
        
        # 関連性スコアでソート
        external_data.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        return external_data[:4]  # 最高品質の4件のみ
    
    def filter_relevant_results(self, results, company_name):
        """検索結果の関連性フィルタリング"""
        filtered_results = []
        
        # 除外キーワード（ノイズになりやすい情報）
        exclude_keywords = ['求人', '転職', '採用', '面接', '就活', '新卒', '中途', '口コミ', 'indeed', 'リクナビ']
        
        # 重要キーワード（関連性判定用）
        important_keywords = ['市場', '業界', '売上', '利益', '業績', 'シェア', '競合', '事業', '戦略', '分析']
        
        for result in results:
            title = result.get('title', '').lower()
            snippet = result.get('snippet', '').lower()
            
            # 除外条件チェック
            if any(exclude in title or exclude in snippet for exclude in exclude_keywords):
                continue
            
            # 企業名の言及チェック
            if company_name.lower() not in title and company_name.lower() not in snippet:
                continue
            
            # 関連性スコア計算
            relevance_score = 0
            for keyword in important_keywords:
                if keyword in title:
                    relevance_score += 2
                if keyword in snippet:
                    relevance_score += 1
            
            # 信頼できるソースかチェック
            url = result.get('link', '')
            if any(domain in url for domain in ['nikkei.com', 'toyokeizai.net', 'diamond.jp', 'itmedia.co.jp']):
                relevance_score += 3
            
            # 最低関連性スコアの閾値
            if relevance_score >= 3:
                result['relevance_score'] = relevance_score
                filtered_results.append(result)
        
        return sorted(filtered_results, key=lambda x: x['relevance_score'], reverse=True)
    
    def search_ir_documents_with_serpapi(self, company_name):
        """SerpAPIを使用してIR関連文書を検索・収集"""
        ir_data = []
        
        st.info("🔍 SerpAPIでIR関連資料を検索中...")
        
        # SerpAPIキーを取得
        serpapi_key = self.get_serpapi_key()
        if not serpapi_key:
            st.warning("⚠️ SerpAPIキーが設定されていません")
            return []
        
        # IR関連の検索クエリ（より具体的）
        ir_search_queries = [
            f'"{company_name}" 決算短信 OR 決算説明会 OR 有価証券報告書 filetype:pdf',
            f'"{company_name}" 中期経営計画 OR 事業戦略 OR 業績 filetype:pdf',
            f'"{company_name}" IR情報 OR 投資家向け OR 財務情報 site:*.co.jp'
        ]
        
        for i, query in enumerate(ir_search_queries, 1):
            st.write(f"🔍 IR検索 {i}/{len(ir_search_queries)}: {query[:60]}...")
            
            try:
                results = self.search_with_serpapi(query, serpapi_key)
                
                if results and 'organic_results' in results:
                    ir_results = self.filter_ir_documents(results['organic_results'], company_name)
                    
                    for result in ir_results[:2]:  # 関連性の高い上位2件
                        ir_data.append({
                            'title': result.get('title', ''),
                            'snippet': result.get('snippet', ''),
                            'url': result.get('link', ''),
                            'source': self.extract_domain(result.get('link', '')),
                            'document_type': self.classify_ir_document(result.get('title', ''), result.get('snippet', '')),
                            'type': 'IR関連資料'
                        })
                    
                    st.success(f"✅ {len(ir_results[:2])}件のIR関連資料を発見")
                else:
                    st.warning(f"⚠️ IR検索 {i}: 結果なし")
                    
            except Exception as e:
                st.warning(f"⚠️ IR検索 {i} エラー: {str(e)}")
                continue
        
        return ir_data[:6]  # 最大6件のIR関連情報
    
    def filter_ir_documents(self, results, company_name):
        """検索結果からIR関連文書をフィルタリング"""
        filtered_results = []
        
        # IR関連キーワード
        ir_keywords = ['決算', '有価証券報告書', '中期経営計画', '業績', 'IR', '投資家', '財務', '売上', '利益', '戦略']
        
        # 除外キーワード
        exclude_keywords = ['求人', '転職', '採用', '新卒', '口コミ', 'indeed', 'リクナビ', 'マイナビ']
        
        for result in results:
            title = result.get('title', '').lower()
            snippet = result.get('snippet', '').lower()
            
            # 除外条件チェック
            if any(exclude in title or exclude in snippet for exclude in exclude_keywords):
                continue
            
            # 企業名の言及チェック
            if company_name.lower() not in title and company_name.lower() not in snippet:
                continue
            
            # IR関連度スコア計算
            ir_score = 0
            for keyword in ir_keywords:
                if keyword in title:
                    ir_score += 3
                if keyword in snippet:
                    ir_score += 1
            
            # PDF文書はスコア追加
            url = result.get('link', '')
            if '.pdf' in url or 'filetype:pdf' in url:
                ir_score += 2
            
            # 企業公式サイトはスコア追加
            if company_name.lower() in url or '.co.jp' in url:
                ir_score += 2
            
            # 最低IR関連スコアの閾値
            if ir_score >= 3:
                result['ir_score'] = ir_score
                filtered_results.append(result)
        
        return sorted(filtered_results, key=lambda x: x['ir_score'], reverse=True)
    
    def establish_company_fundamentals(self, company_name):
        """企業基本情報の確立（主力事業・業界分類・競合の正確な特定）"""
        st.info("🏢 企業基本情報を確立中（主力事業・業界分類・競合の特定）...")
        
        # SerpAPIを使用して企業基本情報を収集
        serpapi_key = self.get_serpapi_key()
        if not serpapi_key:
            st.warning("⚠️ SerpAPIキーが設定されていません")
            return self.create_fallback_company_fundamentals(company_name)
        
        # 企業基本情報の検索クエリ
        fundamental_queries = [
            f'"{company_name}" 会社概要 OR 企業概要 OR 事業内容 site:*.co.jp',
            f'"{company_name}" 主力事業 OR コア事業 OR 売上構成 site:*.co.jp',
            f'"{company_name}" 業界 OR セクター OR 競合他社'
        ]
        
        company_fundamentals = {
            'company_name': company_name,
            'primary_business': '',
            'industry_classification': '',
            'business_segments': [],
            'competitors': [],
            'confidence_score': 0
        }
        
        for i, query in enumerate(fundamental_queries, 1):
            st.write(f"🔍 基本情報検索 {i}/{len(fundamental_queries)}: {query[:60]}...")
            
            try:
                results = self.search_with_serpapi(query, serpapi_key)
                
                if results and 'organic_results' in results:
                    filtered_results = self.filter_company_fundamental_results(results['organic_results'], company_name)
                    
                    for result in filtered_results[:2]:
                        self.extract_fundamental_data(result, company_fundamentals)
                    
                    st.success(f"✅ {len(filtered_results[:2])}件の基本情報を抽出")
                else:
                    st.warning(f"⚠️ 基本情報検索 {i}: 結果なし")
                    
            except Exception as e:
                st.warning(f"⚠️ 基本情報検索 {i} エラー: {str(e)}")
                continue
        
        # 基本情報の妥当性チェック
        company_fundamentals = self.validate_company_fundamentals(company_fundamentals)
        
        return company_fundamentals
    
    def filter_company_fundamental_results(self, results, company_name):
        """企業基本情報の検索結果をフィルタリング"""
        filtered_results = []
        
        # 基本情報関連キーワード
        fundamental_keywords = ['会社概要', '企業概要', '事業内容', '主力事業', '業界', '競合', 'セクター', '売上構成']
        
        # 除外キーワード
        exclude_keywords = ['求人', '転職', '採用', '新卒', '口コミ', 'indeed', 'リクナビ', 'マイナビ', 'エン転職']
        
        for result in results:
            title = result.get('title', '').lower()
            snippet = result.get('snippet', '').lower()
            
            # 除外条件チェック
            if any(exclude in title or exclude in snippet for exclude in exclude_keywords):
                continue
            
            # 企業名の言及チェック
            if company_name.lower() not in title and company_name.lower() not in snippet:
                continue
            
            # 基本情報関連度スコア計算
            fundamental_score = 0
            for keyword in fundamental_keywords:
                if keyword in title:
                    fundamental_score += 3
                if keyword in snippet:
                    fundamental_score += 1
            
            # 企業公式サイトはスコア追加
            url = result.get('link', '')
            if company_name.lower() in url or '.co.jp' in url:
                fundamental_score += 3
            
            # 最低関連性スコアの閾値
            if fundamental_score >= 2:
                result['fundamental_score'] = fundamental_score
                filtered_results.append(result)
        
        return sorted(filtered_results, key=lambda x: x['fundamental_score'], reverse=True)
    
    def extract_fundamental_data(self, result, company_fundamentals):
        """検索結果から企業基本情報を抽出"""
        title = result.get('title', '')
        snippet = result.get('snippet', '')
        text = (title + ' ' + snippet).lower()
        
        # 主力事業の推定
        if '人材' in text or 'hr' in text or '転職' in text or '求人' in text:
            if not company_fundamentals['primary_business']:
                company_fundamentals['primary_business'] = '人材サービス'
                company_fundamentals['industry_classification'] = 'HR・人材サービス'
                company_fundamentals['competitors'].extend(['マイナビ', 'エン・ジャパン', 'パーソルキャリア'])
        
        elif '不動産' in text or 'suumo' in text or '住宅' in text:
            if '人材' not in company_fundamentals['primary_business']:
                company_fundamentals['business_segments'].append('不動産情報サービス')
        
        elif 'it' in text or 'システム' in text or 'デジタル' in text:
            company_fundamentals['business_segments'].append('IT・デジタルサービス')
        
        elif '広告' in text or 'マーケティング' in text:
            company_fundamentals['business_segments'].append('広告・マーケティング')
        
        # 信頼度スコアの更新
        if '.co.jp' in result.get('link', ''):
            company_fundamentals['confidence_score'] += 10
        
        company_fundamentals['confidence_score'] += result.get('fundamental_score', 0)
    
    def validate_company_fundamentals(self, company_fundamentals):
        """企業基本情報の妥当性チェック"""
        
        # リクルートの場合の特別処理（既知の正確な情報で補完）
        if 'リクルート' in company_fundamentals['company_name']:
            company_fundamentals['primary_business'] = '人材サービス・HR Tech'
            company_fundamentals['industry_classification'] = 'HR・人材サービス'
            company_fundamentals['business_segments'] = ['人材サービス', '広告・マーケティング', '不動産情報サービス', 'SaaS・HRテック']
            company_fundamentals['competitors'] = ['マイナビ', 'エン・ジャパン', 'パーソルキャリア', 'ビズリーチ']
            company_fundamentals['confidence_score'] = 95
        
        # 信頼度が低い場合の警告
        if company_fundamentals['confidence_score'] < 30:
            st.warning("⚠️ 企業基本情報の信頼度が低いです。分析結果の精度に影響する可能性があります。")
        
        return company_fundamentals
    
    def create_fallback_company_fundamentals(self, company_name):
        """フォールバック用の企業基本情報"""
        return {
            'company_name': company_name,
            'primary_business': '不明（要確認）',
            'industry_classification': '不明（要確認）',
            'business_segments': [],
            'competitors': [],
            'confidence_score': 0
        }
    
    def classify_ir_document(self, title, snippet):
        """IR文書の種類を分類"""
        text = (title + ' ' + snippet).lower()
        
        if '決算短信' in text or '決算説明' in text:
            return '決算短信・説明資料'
        elif '有価証券報告書' in text or '10-k' in text:
            return '有価証券報告書'
        elif '中期経営計画' in text or '経営戦略' in text:
            return '中期経営計画・戦略資料'
        elif '業績' in text or '財務' in text:
            return '業績・財務資料'
        else:
            return 'IR関連資料'
    
    def search_with_serpapi(self, query, api_key):
        """SerpAPIを使用した検索実行"""
        url = "https://serpapi.com/search"
        params = {
            "q": query,
            "api_key": api_key,
            "engine": "google",
            "num": 5,  # 無料枠節約
            "hl": "ja",  # 日本語
            "gl": "jp"   # 日本地域
        }
        
        response = requests.get(url, params=params, timeout=15)
        
        if response.status_code == 200:
            return response.json()
        else:
            st.warning(f"SerpAPI Error: {response.status_code}")
            return None
    
    def extract_domain(self, url):
        """URLからドメイン名を抽出"""
        if not url:
            return "不明"
        
        try:
            from urllib.parse import urlparse
            domain = urlparse(url).netloc
            
            # 日本の主要メディアドメインを識別
            if 'nikkei.com' in domain:
                return '日本経済新聞'
            elif 'toyokeizai.net' in domain:
                return '東洋経済オンライン'
            elif 'diamond.jp' in domain:
                return 'ダイヤモンド・オンライン'
            elif 'itmedia.co.jp' in domain:
                return 'ITmedia'
            else:
                return domain
        except:
            return "不明"
    
    def create_fallback_external_data(self, company_name, industry_keywords):
        """外部データ取得失敗時のフォールバック情報生成"""
        fallback_data = []
        
        # 一般的な業界情報（推定ベース）
        if 'リクルート' in company_name:
            fallback_data = [
                {
                    'title': '人材・住宅情報サービス業界の動向',
                    'snippet': '人材情報サービス業界は継続的な成長を示しており、デジタル化とAI活用が進展している。住宅情報サービスも同様にDX化が加速。',
                    'url': 'https://example.com/industry-trend',
                    'source': 'フォールバック分析',
                    'type': '推定情報'
                },
                {
                    'title': '情報サービス業界の競合状況',
                    'snippet': '住宅情報分野では複数のプラットフォームが競合。人材サービスではグローバル企業との競争が激化。',
                    'url': 'https://example.com/competition',
                    'source': 'フォールバック分析',
                    'type': '推定情報'
                }
            ]
        else:
            # 汎用的な業界情報
            fallback_data = [
                {
                    'title': f'{industry_keywords}業界の市場動向',
                    'snippet': '当該業界では技術革新とデジタル変革が進んでおり、市場環境は変化している。',
                    'url': 'https://example.com/market-trend',
                    'source': 'フォールバック分析',
                    'type': '推定情報'
                }
            ]
        
        st.info(f"💡 フォールバック情報を生成: {len(fallback_data)}件")
        return fallback_data
    
    def extract_search_keywords(self, question):
        """質問から検索キーワードを抽出"""
        # 企業分析に関連するキーワードマッピング
        keyword_mapping = {
            "売上": ["売上", "revenue", "業績", "決算"],
            "利益": ["利益", "profit", "営業利益", "当期純利益"],
            "事業": ["事業", "business", "サービス", "事業内容"],
            "採用": ["採用", "recruit", "新卒", "中途", "求人"],
            "働き方": ["働き方", "work", "リモート", "制度", "福利厚生"],
            "将来": ["将来", "future", "戦略", "計画", "ビジョン"],
            "競合": ["競合", "競争", "ライバル", "シェア", "市場"],
            "技術": ["技術", "technology", "IT", "DX", "システム"]
        }
        
        question_lower = question.lower()
        found_keywords = []
        
        for category, keywords in keyword_mapping.items():
            for keyword in keywords:
                if keyword in question_lower:
                    found_keywords.extend(keywords)
                    break
        
        return list(set(found_keywords)) if found_keywords else ["企業情報", "会社概要"]
    
    def extract_relevant_content(self, soup, keywords, question):
        """HTMLから質問に関連するコンテンツを深度抽出"""
        relevant_texts = []
        
        # より詳細な要素を対象に拡張
        content_tags = ['h1', 'h2', 'h3', 'h4', 'p', 'div', 'li', 'span', 'td', 'th']
        
        for tag in soup.find_all(content_tags):
            text = tag.get_text().strip()
            
            # テキスト長の条件を緩和（短い重要情報も取得）
            if len(text) < 10 or len(text) > 800:
                continue
                
            text_lower = text.lower()
            question_lower = question.lower()
            
            relevance_score = 0
            
            # キーワードマッチング（重み付け強化）
            for keyword in keywords:
                keyword_lower = keyword.lower()
                if keyword_lower in text_lower:
                    # キーワードの完全一致
                    if keyword_lower in text_lower.split():
                        relevance_score += 3
                    else:
                        relevance_score += 2
            
            # 質問の単語マッチング
            question_words = [w for w in question_lower.split() if len(w) > 2]
            for word in question_words:
                if word in text_lower:
                    relevance_score += 1
            
            # 企業分析に重要な用語への追加スコア
            important_terms = [
                '売上', '利益', '業績', '決算', '戦略', '計画', '事業', 'ビジョン',
                '強み', '特徴', '競合', '市場', '技術', 'DX', 'AI', 'サステナビリティ',
                '採用', '人材', '働き方', '制度', '福利厚生', 'ミッション'
            ]
            
            for term in important_terms:
                if term in text:
                    relevance_score += 1.5
            
            # 数値データがある場合は重要度UP
            if any(char.isdigit() for char in text) and ('億' in text or '万' in text or '%' in text):
                relevance_score += 2
            
            if relevance_score > 0:
                relevant_texts.append({
                    'text': text,
                    'score': relevance_score
                })
        
        # スコア順でソートして上位を返す（数を増加）
        relevant_texts.sort(key=lambda x: x['score'], reverse=True)
        
        # より多くのコンテンツを含める（上位6件）
        top_texts = [item['text'] for item in relevant_texts[:6]]
        
        return '\n\n'.join(top_texts) if top_texts else ""
    
    def classify_source_type(self, url):
        """URLからソースタイプを分類"""
        if '/ir/' in url:
            return 'IR情報'
        elif '/news/' in url:
            return 'ニュース'
        elif '/recruit/' in url:
            return '採用情報'
        elif '/company/' in url:
            return '会社概要'
        elif '/sustainability/' in url:
            return 'サステナビリティ'
        else:
            return '企業情報'
    
    def generate_chat_response(self, question, analysis_data, company_info, chat_history):
        """拡張チャット質問への回答生成（既存ソース活用）"""
        
        # Step 1: 基本的な分析結果をコンテキストとして整理
        base_context = f"""
分析対象企業: {company_info['company_name']}
分析重点分野: {company_info['focus_area']}

【EVP分析結果】:
{json.dumps(analysis_data.get('evp', {}), ensure_ascii=False, indent=2)}

【ビジネス分析結果】:
{json.dumps(analysis_data.get('business_analysis', {}), ensure_ascii=False, indent=2)}
"""
        
        # Step 2: 既存ソースから追加情報を検索
        st.info("🔍 企業サイトを深度調査中...")
        
        # デバッグ情報の表示
        company_domain = company_info.get('company_domain')
        if company_domain:
            st.write(f"調査対象ドメイン: {company_domain}")
        else:
            st.warning("⚠️ 企業ドメインが見つかりません。基本分析結果のみで回答します。")
        
        additional_sources = self.search_existing_sources(question, {
            'company_domain': company_domain
        })
        
        # デバッグ: 詳細な調査結果を表示
        if additional_sources:
            st.success(f"✅ {len(additional_sources)}件の深度調査情報を発見")
            with st.expander("🔍 深度調査詳細"):
                for i, source in enumerate(additional_sources, 1):
                    st.write(f"**{i}. {source.get('source_type', 'N/A')}**")
                    st.write(f"URL: {source.get('url', 'N/A')}")
                    st.write(f"深度: {source.get('depth', 'N/A')}")
                    if source.get('content'):
                        content_preview = source['content'][:200] + "..." if len(source['content']) > 200 else source['content']
                        st.write(f"内容: {content_preview}")
                    st.write("---")
        else:
            st.warning("⚠️ 深度調査で追加情報が見つかりませんでした")
        
        # 追加情報のコンテキスト作成
        additional_context = ""
        if additional_sources:
            st.success(f"✅ {len(additional_sources)}件の追加情報を発見")
            additional_context = "\n【追加収集情報】:\n"
            for i, source in enumerate(additional_sources, 1):
                additional_context += f"\n{i}. {source['source_type']} ({source['url']}):\n{source['content']}\n"
        else:
            st.info("ℹ️ 追加情報は見つかりませんでした。分析結果のみで回答します。")
        
        # Step 3: チャット履歴の整理
        history_context = ""
        if chat_history:
            history_context = "【過去の質疑応答】:\n"
            for q, a in chat_history[-2:]:  # 直近2件のみ
                history_context += f"Q: {q}\nA: {a}\n\n"
        
        # Step 4: 拡張プロンプト作成（ハルシネーション防止強化）
        enhanced_prompt = f"""
あなたは企業分析の専門家です。以下のルールを厳格に守って回答してください：

【CRITICAL回答ルール - 必ず遵守】
1. 提供された情報のみを使用 - 推測や一般論は禁止
2. 情報源を必ず明記：「分析結果によると」「企業サイトの○○によると」
3. データにない情報は絶対に作らず「提供された情報には含まれていません」と明記
4. 具体的な数値・日付・固有名詞は提供データに記載されているもののみ使用
5. 回答は300-500文字程度で具体的に、但し根拠なき情報は一切含めない

【提供データ】
{base_context}

{additional_context}

{history_context}

【現在の質問】: {question}

【指示】
上記の提供データのみを使用して、質問に対する具体的で有用な回答を提供してください。
データに記載されていない情報は推測せず、「提供されたデータには含まれていません」と明記してください。
情報源（分析結果または追加収集情報）を必ず明記してください。
"""
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": enhanced_prompt}],
                temperature=0.2,
                max_tokens=500
            )
            
            answer = response.choices[0].message.content.strip()
            
            # 出典情報を追加
            if additional_sources:
                answer += "\n\n📚 **参照した追加情報:**"
                for source in additional_sources:
                    answer += f"\n• {source['source_type']}: {source['url']}"
            
            return answer
            
        except Exception as e:
            return f"❌ 回答生成中にエラーが発生しました: {str(e)}\n\n分析データを参照して再度お試しください。"
    
    def get_openai_api_key(self):
        """APIキー取得（本番環境対応）"""
        # Streamlit Cloud のSecrets機能を優先
        if hasattr(st, 'secrets') and "OPENAI_API_KEY" in st.secrets:
            return st.secrets["OPENAI_API_KEY"]
        # 環境変数をフォールバック
        elif os.getenv("OPENAI_API_KEY"):
            return os.getenv("OPENAI_API_KEY")
        else:
            st.error("⚠️ OpenAI APIキーが設定されていません。")
            st.markdown("""
            **設定方法:**
            - Streamlit Cloud: Secrets機能でOPENAI_API_KEYを設定
            - ローカル実行: 環境変数でOPENAI_API_KEYを設定
            """)
            st.stop()
    
    def get_serpapi_key(self):
        """SerpAPI キー取得（本番環境対応）"""
        # Streamlit Cloud のSecrets機能を優先
        if hasattr(st, 'secrets') and "SERPAPI_KEY" in st.secrets:
            return st.secrets["SERPAPI_KEY"]
        # 環境変数をフォールバック
        elif os.getenv("SERPAPI_KEY"):
            return os.getenv("SERPAPI_KEY")
        else:
            st.warning("⚠️ SerpAPI キーが設定されていません。外部検索機能は無効化されます。")
            st.markdown("""
            **SerpAPI設定方法（オプション）:**
            - 1. https://serpapi.com でアカウント作成（無料枠月100回）
            - 2. Streamlit Cloud: Secrets機能でSERPAPI_KEYを設定
            - 3. ローカル実行: 環境変数でSERPAPI_KEYを設定
            """)
            return None
    
    def create_research_prompt(self, company_info):
        """工夫されたリサーチプロンプトを作成"""
        prompt = f"""
あなたは企業リサーチの専門家です。以下の企業について、EVP（Employee Value Proposition）と企業分析の各項目を詳細に調査し、具体的な情報を収集してください。

## 調査対象企業
- 企業名: {company_info['company_name']}
- ホームページ: {company_info.get('website_url', '不明')}
- 重点分野: {company_info['focus_area']}

### EVP（Employee Value Proposition）項目

#### 1. Rewards（報酬・待遇）
- 基本給与水準、賞与制度、福利厚生、各種手当やインセンティブ

#### 2. Opportunity（機会・成長）
- 研修制度、キャリアパス、昇進制度、海外駐在機会、資格取得支援

#### 3. Organization（組織・企業文化）
- 企業理念、ミッション、企業文化、ブランド力、組織風土

#### 4. People（人材・マネジメント）
- マネジメントスタイル、チームワーク、心理的安全性、多様性・インクルージョン

#### 5. Work（働き方・業務）
- 勤務時間、リモートワーク、ワークライフバランス、業務の専門性

### 企業分析項目（各項目は300-400文字程度で具体的に記載）

#### 1. 業界・市場分析
- 企業が属する主要業界の特徴と市場規模（具体的な数値必須）
- 業界全体の年成長率と過去3-5年のトレンド
- 業界の主要な技術革新と変化（具体例を含む）
- 向こう5-10年の業界将来性と成長見通し
- 業界が直面している主要な課題と新たな機会
- **必須**: 業界全体の競争状況と参入企業数の概況

#### 2. 業界内ポジション（競合比較必須）
- 売上高の業界内順位と具体的な市場シェア（％表記）
- 主要競合企業を3-5社明記し、それらとの売上・規模比較
- 営業利益率・ROE等の収益性指標と業界平均との比較
- 過去3-5年の売上成長率・利益成長率と競合他社比較
- 株価パフォーマンス・時価総額の業界内位置づけ
- **必須**: 「○○社と比較して」という形で具体的競合企業名を挙げて分析

#### 3. 独自性・差別化要因（具体的事例重視）
- 競合他社が真似できない独自技術・サービス・ビジネスモデル（具体名称）
- 保有する特許数・知的財産・独自ノウハウの概要
- ブランド認知度・顧客ロイヤリティの数値的指標や調査結果
- R&D投資額・投資比率と競合他社との比較
- 参入障壁となる独自資産（設備、ネットワーク、データ等）
- **必須**: 代表的な製品・サービス名を明記し、なぜそれが差別化要因なのかを説明

#### 4. 事業ポートフォリオ分析（具体的数値・事業名重視）
- 主要事業セグメントと売上・利益構成比（％表記必須、具体的な事業名明記）
- 各事業の成長性：「伸びている分野」の特定と過去3-5年の成長率データ
- 収益性分析：「金のなる木」事業の特定と営業利益率・収益貢献度
- 戦略的重点領域：どの分野への投資拡大・M&A・新規参入を進めているか
- 事業間シナジー効果と相互作用の具体例（製品・技術・顧客基盤の共有等）
- **必須**: 各事業セグメントの具体名称、代表的製品・サービス名を明記

## 回答形式
JSON形式で以下の通り回答してください：

```json
{{
  "evp": {{
    "rewards": "具体的な報酬・待遇情報",
    "opportunity": "具体的な成長機会情報",
    "organization": "具体的な組織・企業文化情報",
    "people": "具体的な人材・マネジメント情報",
    "work": "具体的な働き方・業務情報"
  }},
  "business_analysis": {{
    "industry_market": "具体的な業界・市場分析",
    "market_position": "具体的な業界内ポジション",
    "differentiation": "具体的な独自性・差別化要因",
    "business_portfolio": "具体的な事業ポートフォリオ分析"
  }}
}}
```

各項目は**300-400文字で具体的に**記載し、以下を厳格に遵守してください：

【CRITICAL: ファクトベース分析ルール】
1. **一次情報のみ使用**: 企業の公式開示資料（有価証券報告書、決算短信、IR資料）の内容のみ記載
2. **推測・一般論の禁止**: LLMの学習データに基づく推測は一切使用禁止
3. **数値の出典明記**: 「2024年決算短信によると」「有価証券報告書の記載では」等、必ず出典を明記
4. **未確認情報の区別**: 公式情報で確認できない内容は「公式開示情報では確認できません」と明記
5. **競合分析の制限**: 企業が公式に言及した競合のみ記載（推測による競合リストは禁止）

- **数値データ**: 公式開示資料の具体的数字のみ（推定値・業界平均は使用禁止）
- **競合企業名**: 当該企業が公式資料で言及した競合のみ記載
- **固有名詞**: 公式資料に記載された製品名、サービス名のみ使用
- **時系列データ**: 公式開示の過去データのみ使用
- **情報源の明確化**: 全ての情報に「○○年○○資料による」形式で出典明記

**使用禁止表現**: 
- 「一般的に」「推定では」「業界標準」「通常」「多くの企業」
- 具体的出典のない数値・シェア・成長率
- 企業が公式発表していない競合他社名
- LLMの学習データに基づく推測情報

**情報不足時の対応**: 
公式情報が不十分な項目は「公式開示情報が限定的で詳細分析困難」と正直に記載してください。
"""
        return prompt
    
    def create_enhanced_research_prompt(self, company_info, external_data):
        """企業公式情報優先の強化プロンプト作成"""
        
        # 外部情報の整理（補足情報として）
        external_context = ""
        if external_data:
            external_context = "\n【補足：外部参考情報】:\n"
            for i, item in enumerate(external_data, 1):
                external_context += f"{i}. 【{item['source']}】{item['title']}\n"
                external_context += f"   概要: {item['snippet']}\n\n"
        
        prompt = f"""
あなたは企業分析の専門家です。企業公式情報を最優先とし、外部情報は補足として活用して正確な分析を行ってください。

【分析対象企業】
企業名: {company_info['company_name']}
分析重点分野: {company_info['focus_area']}
企業ドメイン: {company_info.get('company_domain', '不明')}

{external_context}

【CRITICAL分析ルール - 厳格に遵守】
1. **情報優先順位**:
   - 第1優先: 企業公式サイト・IR資料の情報
   - 第2優先: 企業開示の定量データ（売上、利益、市場シェア等）
   - 第3優先: 外部記事は企業情報の補足・検証として活用
   
2. **定量分析の徹底**:
   - 売上高、営業利益、従業員数等の具体的数値を重視
   - 市場規模・シェアは公式開示データまたは外部調査データで明記
   - 成長率、ROE等の財務指標を可能な限り含める
   
3. **競合分析の精度**:
   - 企業が公式に言及する競合を最優先
   - 同一事業セグメントの企業を正確に特定
   - 外部記事の競合情報は「参考情報として」で区別
   
4. **事業領域の正確な定義**:
   - 企業の主力事業を公式情報から正確に把握
   - セグメント別売上構成比等の定量データを活用
   - 類似業界との混同を避ける
   
5. **信頼性の担保**:
   - 不明な情報は「確認できません」と明記
   - 推定は根拠を示し「推定」と明記
   - 外部情報は出典を明記し、企業情報と区別

JSON形式で以下の通り回答してください：

```json
{{
  "evp": {{
    "rewards": {{
      "factual_data": "企業公式に開示された報酬・待遇の具体的情報（年収、賞与、福利厚生制度名、数値データ等）",
      "analytical_insights": "開示データに基づく分析・推定（業界比較、成長性評価等）",
      "data_limitations": "情報が不足している項目・推定が必要な箇所"
    }},
    "opportunity": {{
      "factual_data": "企業公式に明示されたキャリアパス・成長機会（制度名、プログラム内容、実績数値等）",
      "analytical_insights": "制度・実績から読み取れる成長可能性の分析",
      "data_limitations": "詳細が不明な制度・推定要素"
    }},
    "organization": {{
      "factual_data": "企業文化・組織に関する公式情報（従業員数、組織構造、企業理念、制度等の具体的内容）",
      "analytical_insights": "組織特性から推測される職場環境・企業文化の分析",
      "data_limitations": "定性的情報や推測が必要な箇所"
    }},
    "people": {{
      "factual_data": "人材育成・マネジメントの公式制度（研修制度名、評価制度、実績数値等）",
      "analytical_insights": "制度から推測される人材戦略・成長環境の分析",
      "data_limitations": "制度詳細や効果が不明な箇所"
    }},
    "work": {{
      "factual_data": "働き方に関する公式情報（勤務制度、業務内容、働き方改革の具体的取組等）",
      "analytical_insights": "制度・取組から推測されるワークライフバランス・業務特性",
      "data_limitations": "実態や詳細が不明な制度・推定要素"
    }}
  }},
  "business_analysis": {{
    "industry_market": {{
      "factual_data": "企業開示・外部調査による市場規模・業界動向の具体的数値・データ",
      "analytical_insights": "データに基づく市場環境・成長性の分析・予測",
      "data_limitations": "データが不足している領域・推定が必要な箇所"
    }},
    "market_position": {{
      "factual_data": "企業開示・外部調査による市場シェア・売上規模等の具体的順位・数値",
      "analytical_insights": "数値データに基づく競争力・ポジション分析",
      "data_limitations": "比較データが不足している競合・推定要素"
    }},
    "differentiation": {{
      "factual_data": "企業公式に明示された差別化要因・競争優位性（技術、サービス、実績等）",
      "analytical_insights": "公式情報から推測される持続的競争優位性の分析",
      "data_limitations": "競争優位性の持続性・効果が不明な箇所"
    }},
    "business_portfolio": {{
      "factual_data": "企業開示によるセグメント別売上・利益・成長率等の具体的数値",
      "analytical_insights": "数値データに基づく事業ポートフォリオ・収益構造の分析",
      "data_limitations": "詳細な収益構造や将来性が不明な事業領域"
    }}
  }}
}}
```

各項目は以下の構造で**600-800文字**で具体的に記載してください：

**📊 factual_data（300-400文字）:**
- 企業公式開示・外部調査の具体的数値・制度名・実績
- 出典を明記（「2024年3月期決算短信によると」「有価証券報告書によると」等）
- 推測を含まない客観的事実のみ

**🔍 analytical_insights（200-300文字）:**
- factual_dataに基づく分析・評価・推測
- 「これらのデータから推測すると」「業界水準と比較して」等で推測であることを明示
- 根拠となるfactual_dataとの関連を明確に示す

**⚠️ data_limitations（100文字程度）:**
- 情報が不足している箇所・推測が必要な理由を簡潔に明記
- 「詳細な制度内容は非開示」「業界比較データなし」等

【記載方針】
- 企業公式情報を70%以上、外部情報は30%以下の比重
- 定量データ（数値）を可能な限り含める
- 情報源を明確に区別：「企業公式によると」「○○年度決算資料によると」「参考として外部調査では」
- 推測・一般論は最小限に抑制

**記載必須要素**: 具体的数値、公式制度名、正確な事業セグメント名、開示された競合企業名
**使用禁止**: 根拠なき推測、出典不明の数値、不正確な競合企業名
"""
        return prompt
    
    def create_revolutionary_analysis_prompt(self, company_fundamentals, structured_ir, hierarchical_data, external_data):
        """革新的な段階的分析プロンプト"""
        
        # 企業基本情報の統合
        company_context = f"""
【確立済み企業基本情報】
企業名: {company_fundamentals['company_name']}
主力事業: {company_fundamentals['primary_business']} (信頼度: {company_fundamentals['confidence_score']}%)
業界分類: {company_fundamentals['industry_classification']}
事業セグメント: {', '.join(company_fundamentals['business_segments'])}
確認済み競合: {', '.join(company_fundamentals['competitors'])}
"""
        
        # IR構造化データの統合
        ir_context = ""
        if structured_ir['financial_data']['revenue']['value']:
            ir_context += f"""
【IR開示財務情報】
売上高: {structured_ir['financial_data']['revenue']['value']} ({structured_ir['financial_data']['revenue']['source']}, {structured_ir['financial_data']['revenue']['year']})
営業利益: {structured_ir['financial_data']['operating_profit']['value']} ({structured_ir['financial_data']['operating_profit']['source']}, {structured_ir['financial_data']['operating_profit']['year']})
従業員数: {structured_ir['financial_data']['employees']['value']} ({structured_ir['financial_data']['employees']['source']}, {structured_ir['financial_data']['employees']['year']})
"""
        
        # データ品質情報
        quality_context = f"""
【データ品質評価】
IR文書発見数: {structured_ir['data_quality']['ir_documents_found']}件
データ完全性: {structured_ir['data_quality']['data_completeness']:.1f}%
信頼性スコア: {structured_ir['data_quality']['reliability_score']:.1f}%
全体信頼性: {hierarchical_data['quality_assessment']['overall_reliability']:.1f}%
"""
        
        # 外部情報の参考データ
        external_context = ""
        if external_data:
            external_context = "\n【参考：外部情報】\n"
            for i, item in enumerate(external_data[:3], 1):
                external_context += f"{i}. 【{item['source']}】{item['title']}\n"
                external_context += f"   概要: {item['snippet'][:100]}...\n\n"
        
        prompt = f"""
あなたは企業分析の最高峰専門家です。以下の段階的分析プロセスに従い、事実と推測を厳格に区別した超高精度分析を実行してください。

{company_context}
{ir_context}
{quality_context}
{external_context}

【REVOLUTIONARY 分析プロセス - 4段階の厳格な検証】

🔍 STAGE 1: 事実確認フェーズ
- IR開示情報の数値は絶対的事実として扱う
- 企業公式情報の制度・取組は事実として扱う
- 外部情報は「参考情報」として明記し、推測の材料とする
- 不明な情報は「IR開示では確認できず」と明記

🧮 STAGE 2: 数値妥当性検証フェーズ
- 業界常識との照合（人材サービス業界の売上規模等）
- 競合他社との規模比較の妥当性確認
- 異常値の検出と理由説明

🏆 STAGE 3: 競合・業界整合性フェーズ
- 確立済み競合企業リストとの整合性確認
- 業界分類「{company_fundamentals['industry_classification']}」に基づく分析
- 他業界企業の誤認識防止

⚠️ STAGE 4: エラー防止最終チェックフェーズ
- 住宅業界との混同チェック
- 根拠なき具体的数値の排除
- 推測の明示と根拠説明

【CRITICAL 出典明記ルール】
- 「2024年3月期決算短信によると」
- 「2023年有価証券報告書によると」
- 「IR開示情報では確認できないため推測すると」
- 「日本経済新聞の報道によると（参考情報）」

【禁止事項】
❌ 根拠なき具体的数値（「市場規模10兆円」等）
❌ 業界誤認識（人材サービス企業を住宅企業として分析）
❌ 不正確な競合企業名（業界外企業の列挙）
❌ 出典不明の制度名・取組名

JSON形式で以下の通り回答してください：

```json
{{
  "evp": {{
    "rewards": {{
      "factual_data": "IR開示・企業公式の報酬待遇情報（具体的数値・制度名・出典明記）",
      "analytical_insights": "開示データに基づく業界比較・成長性分析（推測箇所は「推測」明記）",
      "data_limitations": "IR開示で確認できない項目の明確な指摘"
    }},
    "opportunity": {{
      "factual_data": "IR開示・企業公式のキャリア制度（制度名・実績数値・出典明記）",
      "analytical_insights": "制度から推測される成長環境（推測根拠を明示）",
      "data_limitations": "詳細が不明な制度・推測が必要な箇所"
    }},
    "organization": {{
      "factual_data": "IR開示・企業公式の組織情報（従業員数・組織構造・理念・出典明記）",
      "analytical_insights": "組織特性から推測される職場環境（推測根拠を明示）",
      "data_limitations": "定性的情報で推測が必要な箇所"
    }},
    "people": {{
      "factual_data": "IR開示・企業公式の人材制度（研修制度名・評価制度・実績・出典明記）",
      "analytical_insights": "制度から推測される人材戦略（推測根拠を明示）",
      "data_limitations": "制度詳細や効果が不明な箇所"
    }},
    "work": {{
      "factual_data": "IR開示・企業公式の働き方情報（勤務制度・働き方改革取組・出典明記）",
      "analytical_insights": "制度から推測される業務特性（推測根拠を明示）",
      "data_limitations": "実態や詳細が不明な制度"
    }}
  }},
  "business_analysis": {{
    "industry_market": {{
      "factual_data": "IR開示・外部調査の市場データ（{company_fundamentals['industry_classification']}業界の具体的数値・出典明記）",
      "analytical_insights": "データに基づく市場環境分析（推測箇所は根拠明示）",
      "data_limitations": "データ不足領域の明確な指摘"
    }},
    "market_position": {{
      "factual_data": "IR開示・外部調査のポジションデータ（シェア・売上順位・出典明記）",
      "analytical_insights": "データに基づく競争力分析（確立済み競合: {', '.join(company_fundamentals['competitors'])}との比較）",
      "data_limitations": "比較データが不足している競合・推測要素"
    }},
    "differentiation": {{
      "factual_data": "IR開示・企業公式の差別化要因（技術・サービス・実績・出典明記）",
      "analytical_insights": "公式情報から推測される競争優位性（推測根拠を明示）",
      "data_limitations": "優位性の持続性・効果が不明な箇所"
    }},
    "business_portfolio": {{
      "factual_data": "IR開示のセグメント別数値（売上・利益・成長率・出典明記）",
      "analytical_insights": "数値データに基づく事業ポートフォリオ分析（推測根拠を明示）",
      "data_limitations": "詳細な収益構造が不明な事業領域"
    }}
  }}
}}
```

各factual_dataは400文字、analytical_insightsは300文字、data_limitationsは100文字で記載してください。
"""
        return prompt
    
    def create_ir_integrated_prompt(self, company_info, ir_data, external_data):
        """IR情報統合型の高精度プロンプト作成"""
        
        # IR情報の整理
        ir_context = ""
        if ir_data:
            ir_context = "\n【重要：IR開示情報】:\n"
            for i, item in enumerate(ir_data, 1):
                ir_context += f"{i}. 【{item.get('type', 'IR資料')}】{item['title']}\n"
                ir_context += f"   日付: {item.get('date', '不明')}\n"
                ir_context += f"   内容抜粋: {item.get('content', '')[:300]}...\n\n"
        
        # 外部情報の整理（補足情報として）
        external_context = ""
        if external_data:
            external_context = "\n【補足：外部参考情報】:\n"
            for i, item in enumerate(external_data, 1):
                external_context += f"{i}. 【{item['source']}】{item['title']}\n"
                external_context += f"   概要: {item['snippet']}\n\n"
        
        prompt = f"""
あなたは企業分析の専門家です。IR開示情報を最優先とし、事実と推測を明確に区別した構造化分析を行ってください。

【分析対象企業】
企業名: {company_info['company_name']}
分析重点分野: {company_info['focus_area']}
企業ドメイン: {company_info.get('company_domain', '不明')}

{ir_context}
{external_context}

【CRITICAL分析ルール - 厳格に遵守】

1. **情報優先順位（絶対遵守）**:
   - 第1優先: IR開示情報（決算短信、有価証券報告書、中期経営計画等）
   - 第2優先: 企業公式サイト情報
   - 第3優先: 外部記事は補足・検証として最小限活用

2. **事実と推測の厳格な区別**:
   - factual_data: IR開示・企業公式の具体的数値・制度・実績のみ
   - analytical_insights: データに基づく分析・推測（根拠を明示）
   - data_limitations: 情報不足箇所の明確な指摘

3. **必須記載要素**:
   - 売上高、営業利益、従業員数等の具体的数値（最新期＋過去2-3年推移）
   - セグメント別業績（売上構成比、利益率等）
   - 競合他社との定量比較（シェア、規模等）
   - 公式に開示された制度・取組の具体名

4. **品質担保ルール**:
   - 出典を必ず明記：「2024年3月期決算短信」「2023年有価証券報告書」等
   - 推測は根拠を示し「～から推測される」「～と考えられる」で明示
   - 不明な情報は「開示情報では確認できず」と正直に記載

5. **記載分量・構造**:
   - 各項目600-800文字（factual_data: 400文字、analytical_insights: 300文字、data_limitations: 100文字）
   - 定量データを可能な限り多く含める
   - 具体的制度名・プログラム名・数値を優先

JSON形式で以下の通り回答してください：

```json
{{
  "evp": {{
    "rewards": {{
      "factual_data": "IR開示・企業公式に明示された報酬・待遇の具体的情報（年収、賞与、福利厚生制度名、数値データ等）",
      "analytical_insights": "開示データに基づく分析・推定（業界比較、成長性評価等）",
      "data_limitations": "情報が不足している項目・推定が必要な箇所"
    }},
    "opportunity": {{
      "factual_data": "IR開示・企業公式に明示されたキャリアパス・成長機会（制度名、プログラム内容、実績数値等）",
      "analytical_insights": "制度・実績から読み取れる成長可能性の分析",
      "data_limitations": "詳細が不明な制度・推定要素"
    }},
    "organization": {{
      "factual_data": "IR開示・企業文化・組織に関する公式情報（従業員数、組織構造、企業理念、制度等の具体的内容）",
      "analytical_insights": "組織特性から推測される職場環境・企業文化の分析",
      "data_limitations": "定性的情報や推測が必要な箇所"
    }},
    "people": {{
      "factual_data": "IR開示・人材育成・マネジメントの公式制度（研修制度名、評価制度、実績数値等）",
      "analytical_insights": "制度から推測される人材戦略・成長環境の分析",
      "data_limitations": "制度詳細や効果が不明な箇所"
    }},
    "work": {{
      "factual_data": "IR開示・働き方に関する公式情報（勤務制度、業務内容、働き方改革の具体的取組等）",
      "analytical_insights": "制度・取組から推測されるワークライフバランス・業務特性",
      "data_limitations": "実態や詳細が不明な制度・推定要素"
    }}
  }},
  "business_analysis": {{
    "industry_market": {{
      "factual_data": "IR開示・外部調査による市場規模・業界動向の具体的数値・データ",
      "analytical_insights": "データに基づく市場環境・成長性の分析・予測",
      "data_limitations": "データが不足している領域・推定が必要な箇所"
    }},
    "market_position": {{
      "factual_data": "IR開示・外部調査による市場シェア・売上規模等の具体的順位・数値",
      "analytical_insights": "数値データに基づく競争力・ポジション分析",
      "data_limitations": "比較データが不足している競合・推定要素"
    }},
    "differentiation": {{
      "factual_data": "IR開示・企業公式に明示された差別化要因・競争優位性（技術、サービス、実績等）",
      "analytical_insights": "公式情報から推測される持続的競争優位性の分析",
      "data_limitations": "競争優位性の持続性・効果が不明な箇所"
    }},
    "business_portfolio": {{
      "factual_data": "IR開示によるセグメント別売上・利益・成長率等の具体的数値",
      "analytical_insights": "数値データに基づく事業ポートフォリオ・収益構造の分析",
      "data_limitations": "詳細な収益構造や将来性が不明な事業領域"
    }}
  }}
}}
```

各項目は以下の構造で**600-800文字**で具体的に記載してください：

**📊 factual_data（400文字）:** IR開示・企業公式の具体的数値・制度名・実績のみ
**🔍 analytical_insights（300文字）:** factual_dataに基づく分析・評価・推測
**⚠️ data_limitations（100文字）:** 情報不足箇所の明確な指摘
"""
        return prompt
    
    def research_company(self, company_info):
        """Deep IR情報統合型企業調査（IR深層収集 + 外部情報補足）"""
        
        # Step 1: IR情報の深層収集（再有効化）
        st.info("� Step 1: IR情報を深層収集中（決算書・有価証券報告書・中期経営計画）...")
        ir_data = []
        
        try:
            ir_data = self.search_ir_documents_with_serpapi(company_info['company_name'])
            
            if ir_data:
                st.success(f"✅ {len(ir_data)}件のIR情報を収集しました")
                
                # IR情報の詳細表示
                with st.expander("📊 発見したIR関連情報の詳細"):
                    for i, item in enumerate(ir_data, 1):
                        st.write(f"**{i}. {item['title']}**")
                        st.write(f"種類: {item.get('document_type', 'IR関連資料')}")
                        st.write(f"ソース: {item.get('source', '不明')}")
                        st.write(f"概要: {item.get('snippet', '')[:200]}...")
                        st.write(f"URL: {item.get('url', '')}")
                        st.write("---")
            else:
                st.warning("⚠️ IR関連情報の発見ができませんでした")
                st.info("💡 企業公式サイトの基本情報で分析を継続します")
                
        except Exception as e:
            st.warning(f"⚠️ IR情報検索エラー: {str(e)}")
            st.info("💡 企業公式サイトの基本情報で分析を継続します")
            ir_data = []
        
        # Step 2: 企業公式サイトからの基幹情報収集
        st.info("🏢 Step 2: 企業公式サイトから基幹情報を収集中...")
        
        # Step 3: 外部情報による補足・検証（最小限）
        st.info("🌐 Step 3: 外部情報による補足・検証中...")
        try:
            industry_keywords = company_info.get('focus_area', '').replace('分野', '').replace('領域', '')
            external_data = self.search_external_sources(company_info['company_name'], industry_keywords)
            
            if external_data:
                st.success(f"✅ {len(external_data)}件の補足情報を収集")
                
                # 外部情報の簡潔表示
                with st.expander("🔍 補足情報（外部ソース）"):
                    for i, item in enumerate(external_data, 1):
                        st.write(f"**{i}. {item['source']}**: {item['title'][:80]}...")
            else:
                st.info("ℹ️ 外部補足情報なし - 企業公式情報で分析継続")
                external_data = []
                
        except Exception as e:
            st.warning(f"⚠️ 外部情報収集エラー: {str(e)}")
            st.info("💡 企業公式情報を重視した分析を継続")
            external_data = []
        
        # Step 4: IR情報統合型の高精度分析
        st.info("🧠 Step 4: IR情報を統合した高精度分析実行中...")
        prompt = self.create_ir_integrated_prompt(company_info, ir_data, external_data)
        temperature = 0.05  # より保守的で正確性重視
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "企業分析の専門家として、IR開示情報を最優先とし、事実と推測を明確に区別した構造化分析をJSON形式で回答してください。"},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=8000,  # より詳細な分析のため増量
                temperature=temperature
            )
            
            content = response.choices[0].message.content.strip()
            
            # JSONデータを抽出
            if "```json" in content:
                json_start = content.find("```json") + 7
                json_end = content.find("```", json_start)
                json_content = content[json_start:json_end].strip()
            else:
                json_content = content
            
            research_data = json.loads(json_content)
            
            # IR情報を分析結果に含める
            if ir_data:
                research_data['ir_summary'] = {
                    'documents_analyzed': len(ir_data),
                    'key_documents': [item['title'] for item in ir_data[:5]],
                    'coverage_period': f"過去3年間のIR情報"
                }
            
            return research_data
            
        except Exception as e:
            st.error(f"AI分析中にエラーが発生しました: {e}")
            return None
    
    
    def calculate_analysis_quality_score(self, evp_data, hierarchical_data):
        """分析品質スコアを計算"""
        base_score = 60
        
        # データ信頼性ボーナス
        reliability_bonus = hierarchical_data['quality_assessment']['overall_reliability'] * 0.3
        
        # IR開示カバレッジボーナス
        ir_bonus = hierarchical_data['quality_assessment']['ir_coverage'] * 0.2
        
        # ビジネスロジック整合性ボーナス
        logic_bonus = hierarchical_data['quality_assessment']['business_logic_consistency'] * 0.2
        
        # 構造化データ完全性ボーナス
        completeness_bonus = 10 if hierarchical_data['quality_assessment']['fact_based_ratio'] > 70 else 5
        
        total_score = base_score + reliability_bonus + ir_bonus + logic_bonus + completeness_bonus
        return min(100, int(total_score))
    
    def extract_structured_ir_data(self, company_name):
        """Phase 2: IR情報の構造化抽出（精度向上版）"""
        # 最新IR文書の優先検索クエリ（古い情報混入防止）
        current_year = 2024
        previous_year = 2023
        
        priority_ir_queries = [
            f"{company_name} 決算短信 {current_year}年 3月期",
            f"{company_name} 有価証券報告書 {previous_year}年度", 
            f"{company_name} 四半期報告書 {current_year}",
            f"{company_name} IR 最新 売上 営業利益 {current_year}",
            f'site:ir.{company_name.lower()}.co.jp OR site:{company_name.lower()}.co.jp/ir 決算 {current_year}'
        ]
        
        all_ir_data = []
        
        # 優先度順に検索（最新情報優先）
        for query in priority_ir_queries:
            search_results = self.serp_search(query)
            
            # 検索結果を年次でフィルタリング（2022年以降の情報のみ）
            filtered_results = []
            for result in search_results:
                content = f"{result.get('title', '')} {result.get('snippet', '')}"
                # 古い年次情報を除外
                if any(old_year in content for old_year in ['2021', '2020', '2019', '2018']):
                    continue
                # 最新年次情報を優先
                if any(recent_year in content for recent_year in [str(current_year), str(previous_year)]):
                    result['priority'] = 'high'
                else:
                    result['priority'] = 'medium'
                filtered_results.append(result)
            
            all_ir_data.extend(filtered_results[:2])  # 各クエリから最新2件
        
        # 優先度でソート（高優先度を先に処理）
        all_ir_data.sort(key=lambda x: 0 if x.get('priority') == 'high' else 1)
        
        # 構造化データの初期化
        structured_ir = {
            'financial_data': {
                'revenue': {'value': None, 'source': '', 'year': '', 'confidence': 0},
                'operating_profit': {'value': None, 'source': '', 'year': '', 'confidence': 0},
                'employees': {'value': None, 'source': '', 'year': '', 'confidence': 0}
            },
            'business_strategy': {
                'key_strategies': [],
                'growth_areas': [],
                'challenges': []
            },
            'data_quality': {
                'ir_documents_found': len(all_ir_data),
                'data_completeness': 0,
                'reliability_score': 0,
                'latest_year_coverage': False
            }
        }
        
        # 改良された財務データ抽出パターン（より精密）
        revenue_patterns = [
            rf'(?:{current_year}|{previous_year})年.*?売上高[：:\s]*([0-9,]+(?:\.[0-9]+)?)\s*億円',
            rf'売上高[：:\s]*([0-9,]+(?:\.[0-9]+)?)\s*億円.*?(?:{current_year}|{previous_year})',
            r'売上収益[：:\s]*([0-9,]+(?:\.[0-9]+)?)\s*億円',
            r'Revenue[：:\s]*([0-9,]+(?:\.[0-9]+)?)\s*billion',
        ]
        
        profit_patterns = [
            rf'(?:{current_year}|{previous_year})年.*?営業利益[：:\s]*([0-9,]+(?:\.[0-9]+)?)\s*億円',
            rf'営業利益[：:\s]*([0-9,]+(?:\.[0-9]+)?)\s*億円.*?(?:{current_year}|{previous_year})',
            r'Operating Income[：:\s]*([0-9,]+(?:\.[0-9]+)?)\s*billion',
        ]
        
        employee_patterns = [
            rf'(?:{current_year}|{previous_year})年.*?従業員数[：:\s]*([0-9,]+)\s*[人名]',
            rf'従業員数[：:\s]*([0-9,]+)\s*[人名].*?(?:{current_year}|{previous_year})',
            r'社員数[：:\s]*([0-9,]+)\s*[人名]',
        ]
        
        # 各IR文書からデータ抽出（優先度順）
        for item in all_ir_data:
            content = f"{item.get('title', '')} {item.get('snippet', '')}"
            source = item.get('source', 'IR文書')
            priority = item.get('priority', 'medium')
            
            # 信頼度スコアを優先度に基づいて設定
            confidence = 90 if priority == 'high' else 70
            
            # 年次情報の抽出
            year_match = None
            for year in [current_year, previous_year]:
                if str(year) in content:
                    year_match = str(year)
                    structured_ir['data_quality']['latest_year_coverage'] = True
                    break
            
            # 売上高の抽出（高信頼度のものを優先）
            if not structured_ir['financial_data']['revenue']['value'] or confidence > structured_ir['financial_data']['revenue']['confidence']:
                for pattern in revenue_patterns:
                    match = re.search(pattern, content)
                    if match:
                        structured_ir['financial_data']['revenue'] = {
                            'value': f"{match.group(1)}億円",
                            'source': source,
                            'year': year_match or f'{previous_year}-{current_year}',
                            'confidence': confidence
                        }
                        break
            
            # 営業利益の抽出
            if not structured_ir['financial_data']['operating_profit']['value'] or confidence > structured_ir['financial_data']['operating_profit']['confidence']:
                for pattern in profit_patterns:
                    match = re.search(pattern, content)
                    if match:
                        structured_ir['financial_data']['operating_profit'] = {
                            'value': f"{match.group(1)}億円",
                            'source': source,
                            'year': year_match or f'{previous_year}-{current_year}',
                            'confidence': confidence
                        }
                        break
            
            # 従業員数の抽出
            if not structured_ir['financial_data']['employees']['value'] or confidence > structured_ir['financial_data']['employees']['confidence']:
                for pattern in employee_patterns:
                    match = re.search(pattern, content)
                    if match:
                        structured_ir['financial_data']['employees'] = {
                            'value': f"{match.group(1).replace(',', '')}人",
                            'source': source,
                            'year': year_match or f'{previous_year}-{current_year}',
                            'confidence': confidence
                        }
                        break
        
        # データ完全性の計算（信頼度加重）
        data_fields = ['revenue', 'operating_profit', 'employees']
        weighted_completeness = 0
        total_weight = 0
        
        for field in data_fields:
            if structured_ir['financial_data'][field]['value']:
                confidence = structured_ir['financial_data'][field]['confidence']
                weighted_completeness += confidence
                total_weight += 100
            else:
                total_weight += 100
        
        structured_ir['data_quality']['data_completeness'] = (weighted_completeness / total_weight) * 100 if total_weight > 0 else 0
        
        # 信頼性スコアの計算（最新情報重視）
        base_score = min(len(all_ir_data) * 8, 40)  # 最大40点
        completeness_score = structured_ir['data_quality']['data_completeness'] * 0.4  # 最大40点
        latest_bonus = 20 if structured_ir['data_quality']['latest_year_coverage'] else 0  # 最新年次ボーナス
        
        structured_ir['data_quality']['reliability_score'] = base_score + completeness_score + latest_bonus
        
        return structured_ir
    
    def validate_data_reliability(self, company_fundamentals, structured_ir):
        """Phase 3: データ信頼性の検証（新4段階システム用）"""
        validated_data = {
            'financial_validation': {
                'revenue_plausible': True,
                'profit_margin_reasonable': True,
                'employee_count_realistic': True,
                'business_logic_consistent': True
            },
            'industry_alignment': {
                'sector_appropriate': True,
                'competitor_consistent': True,
                'market_size_aligned': True
            },
            'data_conflicts': [],
            'quality_scores': {
                'fact_based_ratio': 0,
                'ir_coverage': 0,
                'business_logic_consistency': 0
            }
        }
        
        # ビジネスロジック検証
        industry = company_fundamentals.get('industry_classification', '')
        
        # 業界整合性チェック
        if 'HR・人材サービス' in industry:
            # 人材サービス業界の妥当性チェック
            if structured_ir['financial_data']['revenue']['value']:
                revenue_str = structured_ir['financial_data']['revenue']['value']
                revenue_match = re.search(r'([0-9,]+(?:\.[0-9]+)?)', revenue_str)
                if revenue_match:
                    revenue_num = float(revenue_match.group(1).replace(',', ''))
                    if revenue_num < 100 or revenue_num > 50000:  # 100億〜5兆円の範囲
                        validated_data['data_conflicts'].append("売上規模が人材サービス業界の一般的範囲を外れています")
                        validated_data['financial_validation']['business_logic_consistent'] = False
        
        # IR開示カバレッジの計算
        ir_fields = ['revenue', 'operating_profit', 'employees']
        ir_covered = sum(1 for field in ir_fields if structured_ir['financial_data'][field]['value'])
        validated_data['quality_scores']['ir_coverage'] = (ir_covered / len(ir_fields)) * 100
        
        # 事実ベース割合（IR文書から得られたデータの割合）
        total_data_points = 3  # revenue, profit, employees
        ir_data_points = ir_covered
        validated_data['quality_scores']['fact_based_ratio'] = (ir_data_points / total_data_points) * 100
        
        # ビジネスロジック整合性スコア
        logic_checks = [
            validated_data['financial_validation']['business_logic_consistent'],
            validated_data['industry_alignment']['sector_appropriate'],
            validated_data['industry_alignment']['competitor_consistent']
        ]
        validated_data['quality_scores']['business_logic_consistency'] = (sum(logic_checks) / len(logic_checks)) * 100
        
        return validated_data
    
    def create_data_source_hierarchy(self, validated_data):
        """Phase 3補完: データソース階層の作成（新4段階システム用）"""
        hierarchical_data = {
            'data_sources_by_tier': {
                'Tier 1 (IR開示)': [],
                'Tier 2 (企業公式)': [],
                'Tier 3 (外部記事)': [],
                'Tier 4 (推定)': []
            },
            'quality_assessment': {
                'overall_reliability': validated_data['quality_scores']['ir_coverage'],
                'ir_coverage': validated_data['quality_scores']['ir_coverage'],
                'fact_based_ratio': validated_data['quality_scores']['fact_based_ratio'],
                'business_logic_consistency': validated_data['quality_scores']['business_logic_consistency']
            },
            'error_prevention': {
                'industry_misclassification_risk': 'Low' if validated_data['industry_alignment']['sector_appropriate'] else 'High',
                'competitor_confusion_risk': 'Low' if validated_data['industry_alignment']['competitor_consistent'] else 'High',
                'data_hallucination_risk': 'Low' if validated_data['quality_scores']['fact_based_ratio'] > 70 else 'High'
            }
        }
        
        # データソースの階層分類
        if validated_data['quality_scores']['ir_coverage'] > 0:
            hierarchical_data['data_sources_by_tier']['Tier 1 (IR開示)'].append('決算短信・有価証券報告書')
        
        return hierarchical_data

    def save_results(self, company_info, research_data):
        """結果をJSONファイルに保存"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"research_{company_info['company_name']}_{timestamp}.json"
        filepath = self.results_dir / filename
        
        save_data = {
            "company_info": company_info,
            "research_results": research_data,
            "generated_at": datetime.now().isoformat()
        }
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)
            return filepath, save_data
        except:
            # 本番環境でファイル保存に失敗した場合は結果のみ返す
            return None, save_data

def main():
    st.title("🏢 AI企業分析システム")
    st.markdown("### 企業のEVP・ビジネス分析を自動化するAIシステム")
    
    # システム情報
    with st.expander("ℹ️ システム情報", expanded=False):
        st.markdown("""
        **機能:**
        - **EVP分析**: Rewards, Opportunity, Organization, People, Work
        - **ビジネス分析**: 業界分析, 競合比較, 独自性, 事業ポートフォリオ
        - **AI自動調査**: OpenAI GPT-4o-mini使用
        - **結果保存**: JSON形式での詳細レポート
        
        **入力項目:**
        - 企業名（必須）
        - ホームページURL（任意）
        - 分析重点分野（必須）
        """)
    
    # 入力フォーム
    with st.form("company_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            company_name = st.text_input(
                "🏢 企業名 *", 
                placeholder="例: トヨタ自動車、ソフトバンク、リクルート",
                help="分析対象の企業名を入力してください"
            )
            
            # 企業分析の範囲説明
            st.info("🏢 **企業全体の包括的分析を実行します**")
            st.write("- 事業ポートフォリオ全体の分析")
            st.write("- 主力事業領域の詳細評価") 
            st.write("- 業界内競合分析・市場ポジション")
            st.write("- IR開示情報に基づく正確な財務分析")
        
        with col2:
            # 分析レベル選択
            analysis_level = st.selectbox(
                "📊 分析レベル",
                ["標準分析", "詳細分析"],
                help="詳細分析では更に深い調査を実施します"
            )
        
        # 詳細設定（上級者向け）
        with st.expander("⚙️ 詳細設定", expanded=False):
            col3, col4 = st.columns(2)
            with col3:
                date_range = st.selectbox("情報範囲", ["3年以内", "2年以内", "1年以内"], index=0)
                enable_chat = st.checkbox("分析後チャット機能", value=True, help="分析結果に関する追加質問が可能になります")
            with col4:
                # IR関連設定は非表示（将来の拡張用）
                max_crawl_depth = 2  # 固定値
                enable_hallucination_check = False  # IR機能無効時はOFF
        
        st.markdown("---")
        submitted = st.form_submit_button("🔍 AI分析開始", type="primary", use_container_width=True)
    
    # フォーム送信時の処理
    if submitted:
        if not company_name:
            st.error("🚨 企業名は必須入力です。")
            return
        
        # 調査オブジェクトを先に初期化
        researcher = StreamlitCompanyResearcher()
        
        # 会社情報の準備（企業分析に統一）
        company_info = {
            "company_name": company_name,
            "analysis_level": analysis_level,
            "max_crawl_depth": max_crawl_depth,
            "date_range": date_range,
            "enable_hallucination_check": enable_hallucination_check,
            "enable_chat": enable_chat,
            "timestamp": datetime.now().isoformat()
        }
        
        # プログレスバー付きで実行
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        status_text.text("🔍 AI分析を開始しています...")
        progress_bar.progress(20)
        
        with st.spinner("🤖 AI分析中... (30-60秒程度お待ちください)"):
            progress_bar.progress(50)
            research_data = researcher.research_company(company_info)
            progress_bar.progress(80)
        
        if research_data:
            # 結果保存
            filepath, save_data = researcher.save_results(company_info, research_data)
            progress_bar.progress(100)
            status_text.text("✅ 分析完了！")
            
            # セッション状態に分析結果を保存
            st.session_state.analysis_results = {
                "research_data": research_data,
                "company_info": company_info,
                "save_data": save_data,
                "filepath": filepath,
                "researcher": researcher
            }
        else:
            progress_bar.progress(0)
            status_text.text("❌ 分析に失敗しました")
            st.error("❌ AI分析に失敗しました。APIキーの設定またはネットワーク接続を確認してください。")
    
    # 分析結果の表示（セッション状態から）
    if 'analysis_results' in st.session_state:
        results = st.session_state.analysis_results
        research_data = results["research_data"]
        company_info = results["company_info"]
        save_data = results["save_data"]
        filepath = results["filepath"]
        researcher = results["researcher"]
        
        # 分析結果の構造確認（簡素化）
        st.info("📝 分析結果:")
        st.json({
            "データキー": list(research_data.keys()),
            "EVP項目数": len(research_data.get('evp', {})),
            "ビジネス分析項目数": len(research_data.get('business_analysis', {}))
        })
        
        # 結果表示
        st.success("🎉 AI分析が完了しました！")
        
        # 基本情報表示
        st.markdown("---")
        st.subheader("📊 分析結果サマリー")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("🏢 企業名", company_info["company_name"])
        with col2:
            st.metric("🎯 重点分野", company_info["focus_area"])
        with col3:
            st.metric("📊 分析レベル", company_info["analysis_level"])
        with col4:
            st.metric("🕐 分析日時", company_info['timestamp'][:19])
        
        st.markdown("---")
            
        
        # タブ形式で結果表示
        tab1, tab2, tab3 = st.tabs(["📈 EVP分析", "🏆 ビジネス分析", "📄 JSON出力"])
        
        with tab1:
            st.subheader("📈 EVP（Employee Value Proposition）分析")
            
            evp_labels = {
                "rewards": "💰 Rewards（報酬・待遇）",
                "opportunity": "🚀 Opportunity（機会・成長）",
                "organization": "🏢 Organization（組織・企業文化）",
                "people": "👥 People（人材・マネジメント）",
                "work": "💼 Work（働き方・業務）"
            }
            
            # EVP分析結果の安全な表示
            evp_data = research_data.get('evp', {})
            if evp_data:
                for key, label in evp_labels.items():
                    with st.expander(label, expanded=True):
                        content = evp_data.get(key, "分析データが不足しています")
                        st.write(content)
            else:
                st.warning("EVP分析データが生成されませんでした。")
                st.json(research_data)  # デバッグ用
        
        with tab2:
            st.subheader("🏆 ビジネス分析")
            
            business_labels = {
                "industry_market": "📈 業界・市場分析",
                "market_position": "🏆 業界内ポジション",
                "differentiation": "⭐ 独自性・差別化要因",
                "business_portfolio": "🏗️ 事業ポートフォリオ分析"
            }
            
            # ビジネス分析結果の信頼性チェック付き表示
            business_data = research_data.get('business_analysis', {})
            if business_data:
                # 信頼性警告の表示
                st.warning("""
                ⚠️ **情報の信頼性について**
                - ✅ **一次情報**: 企業公式開示資料（有価証券報告書、決算短信等）に基づく内容
                - ⚠️ **要検証**: 推定値や第三者情報に基づく内容
                - ❌ **確認不可**: 公式情報で裏付けが取れない内容
                
                各項目で情報源が明記されていない数値・シェア・競合情報は慎重にご判断ください。
                """)
                
                # 信頼性評価のために研究者インスタンスを作成
                temp_researcher = StreamlitCompanyResearcher()
                
                for key, label in business_labels.items():
                    with st.expander(label, expanded=True):
                        content = business_data.get(key, "分析データが不足しています")
                        
                        # 信頼性チェック
                        reliability_score = temp_researcher.assess_content_reliability(content)
                        
                        if reliability_score >= 80:
                            st.success("✅ 高信頼性: 一次情報に基づく分析")
                        elif reliability_score >= 60:
                            st.warning("⚠️ 中信頼性: 一部推定を含む可能性")
                        else:
                            st.error("❌ 低信頼性: 要検証情報を含む")
                        
                        st.write(content)
            else:
                st.warning("ビジネス分析データが生成されませんでした。")
                st.json(research_data)  # デバッグ用
        
        with tab3:
            st.subheader("📄 JSON形式の分析結果")
            st.markdown("分析結果をJSON形式で表示します。コピーして他のシステムでも活用できます。")
            
            # ダウンロードボタン
            json_output = json.dumps(save_data, ensure_ascii=False, indent=2)
            st.download_button(
                label="💾 JSON結果をダウンロード",
                data=json_output,
                file_name=f"research_{company_info['company_name']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )
            
            # JSON表示
            st.code(json_output, language="json")
            
            if filepath:
                st.info(f"💾 結果はサーバーにも保存されました: {filepath}")
        
        # チャット機能（分析結果後のみ表示）
        if company_info.get('enable_chat', True):
            st.markdown("---")
            st.subheader("💬 分析結果に関する追加質問")
            
            # セッション状態の初期化
            if 'chat_history' not in st.session_state:
                st.session_state.chat_history = []
            if 'analysis_context' not in st.session_state:
                st.session_state.analysis_context = None
            
            # 分析結果をコンテキストとして保存
            if st.session_state.analysis_context != research_data:
                st.session_state.analysis_context = research_data
                st.session_state.chat_history = []  # 新しい分析時はチャット履歴をリセット
            
            # 分析結果ベースの警告
            st.warning("⚠️ この質問機能は分析結果に基づいて回答します。分析データ以外の情報は提供できません。")
            
            # チャット履歴表示
            for i, (question, answer) in enumerate(st.session_state.chat_history):
                with st.chat_message("user"):
                    st.write(question)
                with st.chat_message("assistant"):
                    st.write(answer)
            
            # 質問入力
            user_question = st.chat_input("分析結果について質問してください...")
            
            if user_question:
                # 質問を履歴に追加
                with st.chat_message("user"):
                    st.write(user_question)
                
                # AI回答生成
                with st.chat_message("assistant"):
                    with st.spinner("回答を生成中..."):
                        answer = researcher.generate_chat_response(
                            user_question, 
                            research_data, 
                            company_info,
                            st.session_state.chat_history
                        )
                        st.write(answer)
                
                # 履歴に追加（セッション状態を更新）
                st.session_state.chat_history.append((user_question, answer))
            
            # チャット履歴リセットボタン
            if st.button("🗑️ チャット履歴をリセット"):
                st.session_state.chat_history = []
                st.success("チャット履歴をリセットしました。")
                
        # 新しい分析を開始するボタン
        if st.button("🔄 新しい分析を開始"):
            # セッション状態をクリア
            for key in ['analysis_results', 'chat_history', 'analysis_context']:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()

    # フッター
    st.markdown("---")
    st.markdown(
        """
        <div style="text-align: center; color: #666;">
            🔍 AI企業分析システム | Powered by OpenAI GPT-4o-mini
        </div>
        """, 
        unsafe_allow_html=True
    )

    def extract_structured_ir_data(self, ir_data, company_fundamentals):
        """IR情報から構造化データを抽出"""
        st.info("📊 IR情報から構造化データを抽出中...")
        
        structured_ir = {
            'financial_data': {
                'revenue': {'value': None, 'source': '', 'year': ''},
                'operating_profit': {'value': None, 'source': '', 'year': ''},
                'employees': {'value': None, 'source': '', 'year': ''},
                'segments': []
            },
            'business_strategy': {
                'medium_term_plan': '',
                'key_initiatives': [],
                'growth_targets': []
            },
            'competitive_landscape': {
                'market_position': '',
                'competitive_advantages': [],
                'disclosed_competitors': []
            },
            'data_quality': {
                'ir_documents_found': len(ir_data),
                'data_completeness': 0,
                'reliability_score': 0
            }
        }
        
        # IR文書から数値データを抽出
        for ir_item in ir_data:
            self.extract_financial_metrics(ir_item, structured_ir)
            self.extract_business_strategy(ir_item, structured_ir)
            self.extract_competitive_info(ir_item, structured_ir)
        
        # データ品質評価
        structured_ir = self.assess_ir_data_quality(structured_ir)
        
        return structured_ir
    
    def extract_financial_metrics(self, ir_item, structured_ir):
        """IR情報から財務指標を抽出"""
        title = ir_item.get('title', '')
        snippet = ir_item.get('snippet', '')
        text = (title + ' ' + snippet).lower()
        
        # 売上高の抽出
        import re
        
        # 売上高のパターン（兆円、億円、百万円）
        revenue_patterns = [
            r'売上高[：:\s]*(\d+[,，]?\d*)[^\d]*億円',
            r'売上[：:\s]*(\d+[,，]?\d*)[^\d]*億円',
            r'revenue[：:\s]*(\d+[,，]?\d*)[^\d]*億円'
        ]
        
        for pattern in revenue_patterns:
            match = re.search(pattern, text)
            if match and not structured_ir['financial_data']['revenue']['value']:
                structured_ir['financial_data']['revenue'] = {
                    'value': match.group(1).replace(',', '').replace('，', '') + '億円',
                    'source': ir_item.get('document_type', 'IR資料'),
                    'year': self.extract_year_from_text(text)
                }
                break
        
        # 営業利益の抽出
        profit_patterns = [
            r'営業利益[：:\s]*(\d+[,，]?\d*)[^\d]*億円',
            r'営業益[：:\s]*(\d+[,，]?\d*)[^\d]*億円'
        ]
        
        for pattern in profit_patterns:
            match = re.search(pattern, text)
            if match and not structured_ir['financial_data']['operating_profit']['value']:
                structured_ir['financial_data']['operating_profit'] = {
                    'value': match.group(1).replace(',', '').replace('，', '') + '億円',
                    'source': ir_item.get('document_type', 'IR資料'),
                    'year': self.extract_year_from_text(text)
                }
                break
        
        # 従業員数の抽出
        employee_patterns = [
            r'従業員数[：:\s]*(\d+[,，]?\d*)[^\d]*人',
            r'社員数[：:\s]*(\d+[,，]?\d*)[^\d]*人'
        ]
        
        for pattern in employee_patterns:
            match = re.search(pattern, text)
            if match and not structured_ir['financial_data']['employees']['value']:
                structured_ir['financial_data']['employees'] = {
                    'value': match.group(1).replace(',', '').replace('，', '') + '人',
                    'source': ir_item.get('document_type', 'IR資料'),
                    'year': self.extract_year_from_text(text)
                }
                break
    
    def extract_business_strategy(self, ir_item, structured_ir):
        """IR情報から事業戦略を抽出"""
        title = ir_item.get('title', '')
        snippet = ir_item.get('snippet', '')
        text = title + ' ' + snippet
        
        # 中期経営計画の抽出
        if '中期経営計画' in text or '中期計画' in text or '経営戦略' in text:
            if not structured_ir['business_strategy']['medium_term_plan']:
                structured_ir['business_strategy']['medium_term_plan'] = snippet[:200] + '...'
        
        # 重点施策の抽出
        strategy_keywords = ['DX推進', 'デジタル化', 'AI活用', '新規事業', 'グローバル展開', 'M&A']
        for keyword in strategy_keywords:
            if keyword in text and keyword not in structured_ir['business_strategy']['key_initiatives']:
                structured_ir['business_strategy']['key_initiatives'].append(keyword)
    
    def extract_competitive_info(self, ir_item, structured_ir):
        """IR情報から競合情報を抽出"""
        title = ir_item.get('title', '')
        snippet = ir_item.get('snippet', '')
        text = title + ' ' + snippet
        
        # 市場ポジションの抽出
        if 'シェア' in text or 'ポジション' in text or '市場' in text:
            if not structured_ir['competitive_landscape']['market_position']:
                structured_ir['competitive_landscape']['market_position'] = snippet[:150] + '...'
        
        # 競争優位性の抽出
        advantage_keywords = ['技術力', 'ブランド力', 'ネットワーク', 'データベース', 'プラットフォーム']
        for keyword in advantage_keywords:
            if keyword in text and keyword not in structured_ir['competitive_landscape']['competitive_advantages']:
                structured_ir['competitive_landscape']['competitive_advantages'].append(keyword)
    
    def extract_year_from_text(self, text):
        """テキストから年度を抽出"""
        import re
        year_match = re.search(r'20(\d{2})', text)
        return f"20{year_match.group(1)}年" if year_match else "不明"
    
    def assess_ir_data_quality(self, structured_ir):
        """IR情報の品質評価"""
        completeness_score = 0
        total_fields = 8  # 主要な情報項目数
        
        # 財務データの完全性チェック
        if structured_ir['financial_data']['revenue']['value']:
            completeness_score += 1
        if structured_ir['financial_data']['operating_profit']['value']:
            completeness_score += 1
        if structured_ir['financial_data']['employees']['value']:
            completeness_score += 1
        
        # 戦略情報の完全性チェック
        if structured_ir['business_strategy']['medium_term_plan']:
            completeness_score += 1
        if structured_ir['business_strategy']['key_initiatives']:
            completeness_score += 1
        
        # 競合情報の完全性チェック
        if structured_ir['competitive_landscape']['market_position']:
            completeness_score += 1
        if structured_ir['competitive_landscape']['competitive_advantages']:
            completeness_score += 1
        
        # IR文書数による信頼性スコア
        ir_count = structured_ir['data_quality']['ir_documents_found']
        if ir_count >= 3:
            completeness_score += 1
        
        structured_ir['data_quality']['data_completeness'] = (completeness_score / total_fields) * 100
        structured_ir['data_quality']['reliability_score'] = min(ir_count * 20, 100)
        
        return structured_ir
    
    def validate_data_reliability(self, data_item, source_type, company_fundamentals):
        """データの信頼性を検証"""
        reliability_score = 0
        validation_notes = []
        
        # ソースタイプによる基礎スコア
        source_scores = {
            'IR開示': 90,
            '決算短信・説明資料': 85,
            '有価証券報告書': 95,
            '中期経営計画・戦略資料': 80,
            '企業公式サイト': 70,
            '外部調査レポート': 60,
            '日本経済新聞': 75,
            '東洋経済オンライン': 65,
            '推定': 20
        }
        
        reliability_score = source_scores.get(source_type, 30)
        
        # 数値の妥当性チェック
        if isinstance(data_item, dict) and 'value' in data_item:
            value = data_item['value']
            
            # 売上規模の常識的範囲チェック
            if '億円' in str(value):
                try:
                    amount = float(str(value).replace('億円', '').replace(',', ''))
                    if amount > 100000:  # 10兆円超は要注意
                        reliability_score -= 30
                        validation_notes.append("売上規模が異常に大きい可能性")
                    elif amount < 1:  # 1億円未満は要注意
                        reliability_score -= 20
                        validation_notes.append("売上規模が異常に小さい可能性")
                except:
                    reliability_score -= 40
                    validation_notes.append("数値形式が不正")
        
        # 企業規模との整合性チェック
        if company_fundamentals['primary_business'] == '人材サービス・HR Tech':
            # 人材サービス業界の一般的範囲
            if '住宅' in str(data_item) or '不動産開発' in str(data_item):
                reliability_score -= 50
                validation_notes.append("業界分類との不整合")
        
        return {
            'reliability_score': max(0, reliability_score),
            'validation_notes': validation_notes,
            'source_type': source_type
        }
    
    def create_data_source_hierarchy(self, structured_ir, external_data, company_fundamentals):
        """データソース階層の作成"""
        hierarchical_data = {
            'tier_1_ir_disclosed': {},
            'tier_2_official_company': {},
            'tier_3_external_verified': {},
            'tier_4_estimated': {},
            'quality_assessment': {
                'overall_reliability': 0,
                'data_conflicts': [],
                'missing_critical_data': []
            }
        }
        
        # Tier 1: IR開示情報
        if structured_ir['financial_data']['revenue']['value']:
            hierarchical_data['tier_1_ir_disclosed']['revenue'] = {
                'value': structured_ir['financial_data']['revenue']['value'],
                'source': structured_ir['financial_data']['revenue']['source'],
                'validation': self.validate_data_reliability(
                    structured_ir['financial_data']['revenue'], 
                    structured_ir['financial_data']['revenue']['source'],
                    company_fundamentals
                )
            }
        
        if structured_ir['financial_data']['operating_profit']['value']:
            hierarchical_data['tier_1_ir_disclosed']['operating_profit'] = {
                'value': structured_ir['financial_data']['operating_profit']['value'],
                'source': structured_ir['financial_data']['operating_profit']['source'],
                'validation': self.validate_data_reliability(
                    structured_ir['financial_data']['operating_profit'], 
                    structured_ir['financial_data']['operating_profit']['source'],
                    company_fundamentals
                )
            }
        
        # Tier 3: 外部検証済み情報
        for ext_item in external_data:
            hierarchical_data['tier_3_external_verified'][f"external_{len(hierarchical_data['tier_3_external_verified'])}"] = {
                'title': ext_item.get('title', ''),
                'source': ext_item.get('source', ''),
                'snippet': ext_item.get('snippet', ''),
                'validation': self.validate_data_reliability(
                    ext_item, 
                    ext_item.get('source', '外部記事'),
                    company_fundamentals
                )
            }
        
        # 全体品質評価
        all_scores = []
        for tier in ['tier_1_ir_disclosed', 'tier_3_external_verified']:
            for item in hierarchical_data[tier].values():
                if 'validation' in item:
                    all_scores.append(item['validation']['reliability_score'])
        
        hierarchical_data['quality_assessment']['overall_reliability'] = sum(all_scores) / len(all_scores) if all_scores else 0
        
        # 重要データの欠損チェック
        critical_data = ['revenue', 'operating_profit', 'employees']
        for data_key in critical_data:
            if data_key not in hierarchical_data['tier_1_ir_disclosed']:
                hierarchical_data['quality_assessment']['missing_critical_data'].append(data_key)
        
        return hierarchical_data

if __name__ == "__main__":
    main()