#!/usr/bin/env python3
"""
企業EVP・企業分析システム - Streamlit Web版（本番環境対応）
"""

import streamlit as st
import os
import json
import datetime
import re
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
            return []
        
        try:
            # 質問に基づいて検索キーワードを生成
            search_keywords = self.extract_search_keywords(question)
            
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
                section_sources = self.deep_explore_section(
                    company_domain, section_type, url_patterns, search_keywords, question
                )
                additional_sources.extend(section_sources)
                
                # 最大12ソースまで（各セクション2-3個）
                if len(additional_sources) >= 12:
                    break
            
            # Step 2: 重要文書の自動発見・取得
            document_sources = self.discover_important_documents(
                company_domain, search_keywords, question
            )
            additional_sources.extend(document_sources)
            
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
        """重要文書の自動発見"""
        documents = []
        
        # よく使われる重要文書のパス
        document_paths = [
            '/ir/library/',
            '/ir/finance/',
            '/ir/brief/',
            '/ir/plan/',
            '/company/plan/',
            '/sustainability/report/',
            '/investor/',
            '/finance/results/',
        ]
        
        for path in document_paths:
            try:
                url = f"https://{domain}{path}"
                response = self.session.get(url, timeout=10)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # PDFや重要文書へのリンクを発見
                    for link in soup.find_all('a', href=True):
                        href = link.get('href')
                        text = link.get_text().strip()
                        
                        # 重要文書のキーワード
                        if any(keyword in text for keyword in 
                               ['決算', '有価証券', '中期計画', '事業報告', '説明資料', 'financial']):
                            
                            if href.startswith('/'):
                                full_url = f"https://{domain}{href}"
                            else:
                                full_url = href
                                
                            documents.append({
                                'url': full_url,
                                'content': f"重要文書: {text}",
                                'source_type': '重要文書',
                                'depth': 'document'
                            })
                            
                        if len(documents) >= 3:
                            break
                            
            except:
                continue
                
        return documents
    
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
        st.info("🔍 関連情報を企業サイトから検索中...")
        additional_sources = self.search_existing_sources(question, {
            'company_domain': company_info.get('company_domain')
        })
        
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
        
        # Step 4: 拡張プロンプト作成
        enhanced_prompt = f"""
あなたは企業分析の専門家です。以下のルールを守って回答してください：

【回答ルール】
1. 提供された分析結果と追加収集情報を優先的に参照
2. 情報源を明記：「分析結果によると」「企業サイトの○○情報によると」
3. データにない情報は「提供された情報には含まれていません」と明記
4. 回答は300-400文字程度で具体的に
5. 情報の出典URL表示（追加情報がある場合）

{base_context}

{additional_context}

{history_context}

現在の質問: {question}

上記の情報を使用して、具体的で有用な回答を提供してください。
情報源が分析結果か追加収集情報かを明記してください。
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

各項目は**300-400文字で具体的に**記載し、以下を必ず含めてください：
- **数値データ**: 売上高、市場シェア、成長率等の具体的数字
- **競合企業名**: 主要競合他社を明記（「○○社と比較して」）
- **固有名詞**: 製品名、サービス名、技術名等の具体名称
- **時系列データ**: 「過去○年で」「近年では」等の変化・トレンド
- **情報源の明確化**: データが不明な場合は「公開情報では確認できず」と明記

**禁止表現**: 「一般的に」「多くの企業と同様」「業界標準的」などの曖昧な表現は使用禁止
"""
        return prompt
    
    def research_company(self, company_info):
        """LLMに企業調査を依頼（IR機能一時無効化、従来方式で安定化）"""
        
        # IR情報収集を一時無効化
        if False:  # IR機能を無効化
            st.info("🔍 IR情報を自動収集中...")
            try:
                crawler = SmartIRCrawler(
                    company_info['company_domain'],
                    company_info.get('ir_top_url'),
                    max_depth=2,
                    date_limit_years=3
                )
                ir_data = crawler.crawl_with_intelligence()
                
                if ir_data:
                    st.success(f"✅ {len(ir_data)}件のIR情報を収集しました")
                else:
                    st.info("ℹ️ IR情報の収集に失敗しました。従来の分析方法を使用します。")
            except Exception as e:
                st.warning(f"⚠️ IR収集エラー: {str(e)} - 従来の分析方法を使用します。")
                ir_data = []
        
        # 従来の安定した分析方式を使用
        st.info("🔍 安定した汎用分析を実行中...")
        prompt = self.create_research_prompt(company_info)
        temperature = 0.3
        ir_data = []  # IR情報をクリア
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "企業リサーチの専門家として、正確で具体的な情報をJSON形式で回答してください。"},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=6000,
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
            
            # IR関連の処理はスキップ
            # 従来通りの分析結果のみ返却
            
            return research_data
            
        except Exception as e:
            st.error(f"AI調査中にエラーが発生しました: {e}")
            return None
    
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
            website_url = st.text_input(
                "🌐 ホームページURL", 
                placeholder="例: https://www.company.co.jp/",
                help="企業の公式サイトURL（IR探索にも使用されます）"
            )
        
        with col2:
            focus_area = st.text_input(
                "🎯 分析重点分野 *", 
                placeholder="例: 新卒採用、エンジニア採用、中途採用",
                help="どの分野に重点を置いて分析するかを指定"
            )
            
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
        if not company_name or not focus_area:
            st.error("🚨 企業名と分析重点分野は必須入力です。")
            return
        
        # 調査オブジェクトを先に初期化
        researcher = StreamlitCompanyResearcher()
        
        # 会社情報の準備
        company_domain = researcher.extract_domain_from_url(website_url)
        company_info = {
            "company_name": company_name,
            "website_url": website_url,
            "company_domain": company_domain,
            "focus_area": focus_area,
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
            
            # ビジネス分析結果の安全な表示
            business_data = research_data.get('business_analysis', {})
            if business_data:
                for key, label in business_labels.items():
                    with st.expander(label, expanded=True):
                        content = business_data.get(key, "分析データが不足しています")
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

if __name__ == "__main__":
    main()