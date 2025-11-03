#!/usr/bin/env python3
"""
🏢 企業ビジネス分析システム - Streamlit Web版
EVP機能を削除し、企業のビジネス分析に特化したAIシステム
"""

import streamlit as st
import os
import json
import time
import requests
from pathlib import Path
from openai import OpenAI
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from datetime import datetime, timedelta
import PyPDF2
import pdfplumber
import io

# ページ設定
st.set_page_config(
    page_title="🏢 企業ビジネス分析システム",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 設定定数
CONFIG = {
    'MAX_CRAWL_DEPTH': 4,  # 4階層維持（重要資料アクセス）
    'DATE_LIMIT_YEARS': 3,
    'MAX_SOURCES': 12,  # 10→12に微増
    'MAX_CONTENT_LENGTH': 50000,  # 100000→50000文字（バランス型）
    'TIME_LIMIT_SECONDS': 180,  # 3分制限を追加
    'PDF_PAGES_LIMIT': 10,  # PDF処理ページ制限
    'USER_AGENT': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
}

class SearchBasedIRCollector:
    """SerpAPI検索ベースのIR情報収集システム"""
    
    def __init__(self, company_name):
        self.company_name = company_name
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': CONFIG['USER_AGENT']})
        self.start_time = None  # 処理時間制限用
    
    def smart_content_filter(self, content):
        """重要情報を優先的に抽出するスマートフィルタ"""
        if not content:
            return content
            
        # 重要キーワード（優先度順）
        priority_keywords = [
            # 財務・業績関連（最重要）
            '売上高', '営業利益', '純利益', '当期純利益', '売上', '利益', '収益',
            '業績', '決算', '財務', '損益', 'EBITDA', 'ROE', 'ROA',
            
            # 市場・事業関連
            '市場シェア', '市場規模', '競合', '事業セグメント', '事業ポートフォリオ',
            '成長率', '前年同期比', '前年比', 'YoY', 'QoQ',
            
            # 戦略・展望関連
            '戦略', '方針', '計画', '展望', '予想', '見通し', '目標',
            'DX', 'デジタル変革', 'AI', 'データ活用'
        ]
        
        # コンテンツを段落に分割
        paragraphs = content.split('\n')
        
        # 各段落にスコアを付与
        scored_paragraphs = []
        for paragraph in paragraphs:
            if len(paragraph.strip()) < 20:  # 短すぎる段落は除外
                continue
                
            score = 0
            paragraph_lower = paragraph.lower()
            
            # キーワードマッチングでスコア計算
            for i, keyword in enumerate(priority_keywords):
                if keyword in paragraph_lower:
                    # 早期のキーワードほど高スコア
                    score += (len(priority_keywords) - i) * 2
            
            # 数値データがある段落は追加ポイント
            if any(char.isdigit() for char in paragraph):
                score += 10
            
            # パーセンテージや円表記がある場合は追加ポイント
            if '%' in paragraph or '円' in paragraph or '億' in paragraph or '兆' in paragraph:
                score += 15
                
            scored_paragraphs.append((score, paragraph))
        
        # スコア順でソート
        scored_paragraphs.sort(key=lambda x: x[0], reverse=True)
        
        # 上位の段落を結合して返す
        filtered_content = '\n'.join([para for score, para in scored_paragraphs])
        
        # 文字数制限を適用
        if len(filtered_content) > CONFIG['MAX_CONTENT_LENGTH']:
            filtered_content = filtered_content[:CONFIG['MAX_CONTENT_LENGTH']] + '...'
            
        return filtered_content
    
    def format_text_for_display(self, text):
        """テキストを読みやすく整形（改行重視・構造化）"""
        if not text or len(text.strip()) == 0:
            return text
            
        # 句点での分割を基本にして段落を作成
        sentences = text.split('。')
        formatted_sentences = []
        
        for i, sentence in enumerate(sentences):
            sentence = sentence.strip()
            if len(sentence) == 0:
                continue
                
            # 句点を復元
            if not sentence.endswith('。') and i < len(sentences) - 1:
                sentence += '。'
            
            formatted_sentences.append(sentence)
            
            # 2-3文ごとに改行を挿入（読みやすさ重視）
            if (i + 1) % 2 == 0 and i < len(sentences) - 2:
                formatted_sentences.append('\n')
        
        # 重要な数値・キーワードをハイライト
        formatted_text = '\n'.join(formatted_sentences)
        return self.highlight_important_info(formatted_text)
    
    def highlight_important_info(self, text):
        """重要な数値・キーワードを太字でハイライト"""
        import re
        
        # 数値関連のハイライト（改行考慮を強化）
        text = re.sub(r'(\d+(?:,\d{3})*億円)', r'**\1**', text)  # 金額
        text = re.sub(r'(\d+(?:,\d{3})*兆円)', r'**\1**', text)  # 大きな金額
        text = re.sub(r'(\d+\.?\d*%)', r'**\1**', text)  # パーセンテージ
        text = re.sub(r'(前年(?:同期)?比[+-]?\d+\.?\d*%)', r'**\1**', text)  # 成長率
        text = re.sub(r'(売上高\d+)', r'**\1**', text)  # 売上
        
        # 重要キーワードのハイライト
        important_keywords = [
            '売上高', '営業利益', '純利益', '当期純利益', 'EBITDA',
            '市場シェア', 'シェア', '市場規模', '成長率',
            '従業員数', '売上構成比', '利益率', 'ROE', 'ROA'
        ]
        
        for keyword in important_keywords:
            # 単語境界を考慮してハイライト
            text = re.sub(f'({re.escape(keyword)})', r'**\1**', text)
        
        return text
    
    def display_formatted_analysis(self, analysis_data):
        """分析結果を構造化して美しく表示"""
        
        # セクション定義（アイコン + 日本語タイトル）
        sections = [
            ("📊", "業界・市場分析", "industry_market", "市場環境、業界動向、成長性に関する分析"),
            ("🎯", "市場ポジション", "market_position", "競合比較、市場シェア、競争優位性"),  
            ("💡", "差別化要因", "differentiation", "独自の強み、技術優位性、ブランド価値"),
            ("🏢", "事業ポートフォリオ", "business_portfolio", "事業構成、収益構造、成長戦略")
        ]
        
        for icon, title, key, description in sections:
            content = analysis_data.get(key, '')
            
            if content and len(content.strip()) > 0:
                # セクションヘッダー
                st.markdown(f"## {icon} {title}")
                st.markdown(f"*{description}*")
                st.markdown("")  # 空行追加
                
                # コンテンツを整形して表示
                formatted_content = self.format_text_for_display(content)
                st.markdown(formatted_content)
                
                # セクション区切り
                st.markdown("---")
                st.markdown("")  # 区切り後の空行
            else:
                # コンテンツがない場合
                st.markdown(f"## {icon} {title}")
                st.info(f"{title}の情報は収集できませんでした。")
                st.markdown("---")
                st.markdown("")
    
    def get_serpapi_key(self):
        """SerpAPIキー取得（本番環境対応）"""
        # 環境変数を最優先でチェック
        env_key = os.getenv("SERPAPI_KEY")
        if env_key and len(env_key) > 10:
            return env_key
        
        # Streamlit Cloud のSecrets機能
        if hasattr(st, 'secrets') and "SERPAPI_KEY" in st.secrets:
            key = st.secrets["SERPAPI_KEY"]
            # テスト値や無効な値でないことを確認
            if key and key != "your-actual-serpapi-key-here" and len(key) > 10 and not key.startswith("test"):
                return key
        
        # SerpAPI未設定時の明確な通知（エラーではなく情報）
        return None
    
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
        
        try:
            response = requests.get(url, params=params, timeout=15)
            
            if response.status_code == 200:
                result = response.json()
                # エラーレスポンスをチェック
                if 'error' in result:
                    st.warning(f"SerpAPI Error: {result['error']}")
                    return {'error': result['error']}
                return result
            elif response.status_code == 401:
                st.error("❌ SerpAPIキーが無効です。Secrets設定を確認してください。")
                return {'error': 'Invalid API Key'}
            elif response.status_code == 429:
                st.warning("⚠️ SerpAPI使用制限に達しました。しばらく待ってから再試行してください。")
                return {'error': 'Rate limit exceeded'}
            else:
                st.warning(f"SerpAPI HTTP Error: {response.status_code}")
                return {'error': f'HTTP {response.status_code}'}
                
        except requests.exceptions.Timeout:
            st.warning("⚠️ SerpAPI接続タイムアウト")
            return {'error': 'Timeout'}
        except requests.exceptions.ConnectionError:
            st.warning("⚠️ SerpAPIに接続できません")
            return {'error': 'Connection Error'}
        except requests.exceptions.RequestException as e:
            st.warning(f"⚠️ SerpAPIリクエストエラー: {str(e)}")
            return {'error': str(e)}
        except Exception as e:
            st.warning(f"⚠️ 予期しないエラー: {str(e)}")
            return {'error': str(e)}
    
    def search_ir_information(self):
        """IR関連情報を検索ベースで収集"""
        import time
        self.start_time = time.time()  # 処理開始時間を記録
        
        serpapi_key = self.get_serpapi_key()
        if not serpapi_key:
            st.info("🔍 SerpAPIキーが未設定のため、OpenAI APIの知識ベースで分析を実行します")
            return []
        
        # IR関連検索クエリ
        search_queries = [
            f"{self.company_name} IR 投資家向け情報",
            f"{self.company_name} 決算 業績 財務",
            f"{self.company_name} 有価証券報告書",
            f"{self.company_name} 事業報告 年次報告書"
        ]
        
        collected_data = []
        successful_searches = 0
        
        for query in search_queries:
            # 時間制限チェック
            if time.time() - self.start_time > CONFIG['TIME_LIMIT_SECONDS']:
                st.warning(f"⏱️ 時間制限({CONFIG['TIME_LIMIT_SECONDS']}秒)に達したため処理を停止しました")
                break
                
            try:
                st.info(f"🔍 検索中: {query}")
                search_results = self.search_with_serpapi(query, serpapi_key)
                
                if search_results and 'organic_results' in search_results:
                    successful_searches += 1
                    for result in search_results['organic_results'][:2]:  # 上位2件のみ
                        # 時間制限チェック
                        if time.time() - self.start_time > CONFIG['TIME_LIMIT_SECONDS']:
                            st.warning(f"⏱️ 時間制限に達したため、残りの処理をスキップします")
                            break
                            
                        url = result.get('link', '')
                        title = result.get('title', '')
                        snippet = result.get('snippet', '')
                        
                        # IR関連URLかチェック
                        if self.is_ir_related_url(url, title):
                            # Webページの内容を取得（拡張版）
                            content = self.fetch_webpage_content(url)
                            if content:
                                # スマートフィルタリングを適用
                                filtered_content = self.smart_content_filter(content)
                                collected_data.append({
                                    'url': url,
                                    'content': filtered_content,  # フィルタリング済みコンテンツ
                                    'title': title,
                                    'snippet': snippet,
                                    'search_query': query
                                })
                                st.success(f"✅ IR情報を取得: {title}")
                elif search_results and 'error' in search_results:
                    st.warning(f"⚠️ 検索エラー: {search_results.get('error', 'Unknown error')}")
                else:
                    st.info(f"📊 検索結果: {query}")
                
                time.sleep(1)  # API制限回避
                
            except requests.exceptions.Timeout:
                st.warning(f"⚠️ 検索タイムアウト: {query}")
                continue
            except requests.exceptions.RequestException as e:
                st.warning(f"⚠️ 検索リクエストエラー: {str(e)}")
                continue
            except Exception as e:
                st.warning(f"⚠️ 予期しないエラー: {str(e)}")
                continue
        
        if collected_data:
            st.success(f"📊 {len(collected_data)}件のIR情報を検索で収集しました（{successful_searches}/{len(search_queries)}件の検索が成功）")
        elif successful_searches > 0:
            st.info("🔍 検索は成功しましたが、IR関連の有用な情報が見つかりませんでした。一般的な公開情報で分析を実行します。")
        else:
            st.warning("⚠️ 検索に失敗しました。一般的な公開情報で分析を実行します。")
        
        return collected_data
    
    def is_ir_related_url(self, url, title):
        """IR関連URLかどうかを判定（PDF含む）"""
        ir_keywords = ['ir', 'investor', '投資家', '決算', '業績', '財務', '有価証券', '年次報告', 
                      'pdf', '報告書', 'report', 'financial', 'annual', 'quarterly']
        url_lower = url.lower()
        title_lower = title.lower()
        
        return any(keyword in url_lower or keyword in title_lower for keyword in ir_keywords)
    
    def fetch_webpage_content(self, url, depth=0):
        """Webページの内容を取得（PDF対応・多階層クロール）"""
        try:
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                content_type = response.headers.get('content-type', '').lower()
                
                # PDF処理
                if 'pdf' in content_type:
                    return self.extract_pdf_content(response.content)
                
                # HTML処理
                soup = BeautifulSoup(response.text, 'html.parser')
                text_content = soup.get_text()
                content = ' '.join(text_content.split())
                
                # 多階層クロール: 深度が制限内でリンクを収集
                if depth < CONFIG['MAX_CRAWL_DEPTH']:
                    sub_content = self.crawl_subpages(soup, url, depth + 1)
                    content += sub_content
                
                # 文字数制限を適用
                return content[:CONFIG['MAX_CONTENT_LENGTH']]
            else:

                return None
        except requests.exceptions.Timeout:

            return None
        except requests.exceptions.RequestException as e:

            return None
        except Exception as e:

            return None
    
    def extract_pdf_content(self, pdf_content):
        """PDFからテキストを抽出"""
        try:
            # pdfplumberを優先使用（レイアウト情報を保持）
            with io.BytesIO(pdf_content) as pdf_stream:
                with pdfplumber.open(pdf_stream) as pdf:
                    text = ""
                    for page in pdf.pages[:CONFIG['PDF_PAGES_LIMIT']]:  # CONFIG設定に従う
                        if page.extract_text():
                            text += page.extract_text() + "\n"
                    
                    if text.strip():
                        return ' '.join(text.split())[:CONFIG['MAX_CONTENT_LENGTH']]
            
            # フォールバック: PyPDF2を使用
            with io.BytesIO(pdf_content) as pdf_stream:
                pdf_reader = PyPDF2.PdfReader(pdf_stream)
                text = ""
                for page_num in range(min(len(pdf_reader.pages), 20)):
                    page = pdf_reader.pages[page_num]
                    text += page.extract_text() + "\n"
                
                return ' '.join(text.split())[:CONFIG['MAX_CONTENT_LENGTH']]
                
        except Exception as e:

            return None
    
    def crawl_subpages(self, soup, base_url, current_depth):
        """サブページを再帰的にクロール"""
        if current_depth >= CONFIG['MAX_CRAWL_DEPTH']:
            return ""
        
        sub_content = ""
        ir_links = []
        
        # IR関連リンクを抽出
        for link in soup.find_all('a', href=True):
            href = link.get('href')
            if href:
                full_url = urljoin(base_url, href)
                link_text = link.get_text().strip()
                
                # IR関連キーワードをチェック
                if self.is_ir_related_url(full_url, link_text) and full_url not in ir_links:
                    ir_links.append(full_url)
                    
                    if len(ir_links) >= 5:  # 各階層で最大5リンク
                        break
        
        # サブページの内容を取得
        for link_url in ir_links:
            time.sleep(0.5)  # レート制限
            subcontent = self.fetch_webpage_content(link_url, current_depth)
            if subcontent:
                sub_content += f"\n[サブページ {current_depth}階層]: {subcontent[:5000]}"  # 各サブページ5000文字まで
        
        return sub_content

class BusinessAnalyzer:
    """企業ビジネス分析システム（事業分析特化）"""
    
    def __init__(self):
        self.client = OpenAI(api_key=self._get_api_key())
        
    def _get_api_key(self):
        """APIキーを取得"""
        # Streamlit Cloudの場合
        if hasattr(st, 'secrets') and 'OPENAI_API_KEY' in st.secrets:
            return st.secrets["OPENAI_API_KEY"]
        
        # 環境変数から
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            st.error("❌ OpenAI APIキーが設定されていません")
            st.stop()
        
        return api_key
    
    def create_analysis_prompt(self, company_name, ir_data=None):
        """統一された分析プロンプト（事業分析のみ）"""
        
        ir_content = ""
        sources_list = []
        if ir_data:
            ir_content = "\n".join([
                f"【IR情報源】: {item['title']}\n出典URL: {item['url']}\n内容: {item['content'][:2400]}...\n"
                for item in ir_data[:3]
            ])
            sources_list = [item['url'] for item in ir_data[:3]]
        
        prompt = f"""
以下の企業について事業分析を実行し、必ず有効なJSON形式で回答してください。

企業名: {company_name}

利用可能な情報:
{ir_content if ir_content else f"【{company_name}】の一般的な公開情報・知識ベースに基づく包括的分析"}

【重要な分析要求】:
- 各項目で2400文字程度の詳細分析を実施してください
- あなたの知識ベースから具体的な数値データ（売上、利益、従業員数、市場シェア等）を必ず含めてください
- 競合他社との比較を定量的に行ってください
- 過去3年間のトレンド分析を含めてください
- 将来予測と戦略的示唆を含めてください
- IR情報が無い場合でも、あなたの知識から最新の企業情報を活用してください

以下の正確なJSON形式で回答してください:

{{
  "business_analysis": {{
    "industry_market": "業界・市場分析の詳細（2400文字程度）- 市場規模、成長率、主要プレイヤー、トレンド、将来予測を含む包括的分析。具体的な数値と統計データを含めること。",
    "market_position": "業界内ポジションの分析（2400文字程度）- 市場シェア、売上ランキング、競合比較、強み・弱みの定量的分析。売上高、利益率、従業員数等の具体的データを含めること。",
    "differentiation": "独自性・差別化要因の分析（2400文字程度）- 技術力、ブランド力、ビジネスモデル、特許、人材等の競争優位性の詳細分析。具体的な事例と数値を含めること。",
    "business_portfolio": "事業ポートフォリオの分析（2400文字程度）- 事業セグメント別売上、利益率、成長性、リスク分析、今後の戦略方向性。具体的な事業別数値と将来予測を含めること。"
  }},
  "analysis_metadata": {{
    "company_name": "{company_name}",
    "analysis_date": "{datetime.now().strftime('%Y-%m-%d')}",
    "data_sources": {sources_list if sources_list else [f"{company_name}の一般的な公開情報・AI知識ベース"]},
    "ir_sources_count": {len(sources_list) if sources_list else 0},
    "reliability_score": {90 if sources_list else 70}
  }}
}}

重要: JSON形式以外の文字は一切含めず、上記の構造に従って有効なJSONのみを出力してください。
各分析項目では具体的な数値、比較データ、トレンド分析を必ず含めてください。
"""
        return prompt
    
    def analyze_company(self, company_name, company_url=None):
        """企業の事業分析を実行（検索ベース）"""
        
        # 検索ベースでIR情報収集
        collector = SearchBasedIRCollector(company_name)
        ir_data = collector.search_ir_information()
        
        # 分析プロンプト作成
        prompt = self.create_analysis_prompt(company_name, ir_data)
        
        try:
            st.info("🤖 AI分析を実行中...")
            
            # JSON形式を強制するための改善されたアプローチ
            response = self.client.chat.completions.create(
                model="gpt-5",
                messages=[
                    {
                        "role": "system", 
                        "content": "あなたは企業分析の専門家です。必ず有効なJSON形式でのみ回答してください。JSONの構文エラーは絶対に避けてください。"
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                max_completion_tokens=12000,  # GPT-5対応パラメータ
                response_format={"type": "json_object"}  # JSON形式を強制
            )
            
            result_text = response.choices[0].message.content
            st.success("✅ AI応答を受信しました")
            
            # デバッグ情報（開発時のみ表示）
            with st.expander("🔍 AI応答の詳細（デバッグ用）", expanded=False):
                st.text(f"応答長: {len(result_text)}文字")
                st.text(f"最初の200文字: {result_text[:200]}...")
                st.text(f"最後の200文字: ...{result_text[-200:]}")
            
            # 直接JSON解析を試行
            try:
                result = json.loads(result_text)
                
                # 必要なキーの存在を確認
                if 'business_analysis' in result:
                    st.success("✅ JSON解析成功")
                    return result
                else:
                    st.warning("⚠️ 必要なキー 'business_analysis' が見つかりません")
                    # フォールバック: 基本構造を作成
                    return self._create_fallback_result(company_name, result_text)
                    
            except json.JSONDecodeError as e:
                st.error(f"❌ 直接JSON解析エラー: {str(e)}")
                # フォールバック処理
                return self._create_fallback_result(company_name, result_text)
                
        except Exception as e:
            st.error(f"❌ AI分析エラー: {str(e)}")
            return None
    
    def _create_fallback_result(self, company_name, raw_text):
        """フォールバック: AIの応答からテキストベースで結果を生成"""
        st.warning("⚠️ JSON解析に失敗しました。テキストベースで結果を生成します。")
        
        with st.expander("📄 生のAI応答", expanded=False):
            st.text(raw_text)
        
        # 基本的な構造化データを作成
        fallback_result = {
            "business_analysis": {
                "industry_market": f"{company_name}の業界・市場分析情報（AI応答の解析に失敗したため、詳細な分析を再実行してください）",
                "market_position": f"{company_name}の市場ポジション情報（AI応答の解析に失敗したため、詳細な分析を再実行してください）",
                "differentiation": f"{company_name}の独自性・差別化情報（AI応答の解析に失敗したため、詳細な分析を再実行してください）",
                "business_portfolio": f"{company_name}の事業ポートフォリオ情報（AI応答の解析に失敗したため、詳細な分析を再実行してください）"
            },
            "analysis_metadata": {
                "company_name": company_name,
                "analysis_date": datetime.now().strftime('%Y-%m-%d'),
                "data_sources": ["解析失敗により不明"],
                "ir_sources_count": 0,
                "reliability_score": 30,
                "error_note": "JSON解析に失敗したため、フォールバック結果を表示しています"
            }
        }
        
        # 生のテキストから有用な情報を抽出を試行
        if raw_text and len(raw_text) > 100:
            # 簡単なテキスト分析で部分的に情報を抽出
            lines = raw_text.split('\n')
            useful_lines = [line.strip() for line in lines if line.strip() and len(line.strip()) > 20]
            
            if useful_lines:
                combined_text = ' '.join(useful_lines[:5])  # 最初の5行を結合
                fallback_result["business_analysis"]["industry_market"] = f"{company_name}に関する情報: {combined_text[:400]}..."
        
        return fallback_result
    
    def save_results(self, company_name, analysis_data):
        """分析結果を保存"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"business_analysis_{company_name}_{timestamp}.json"
            
            save_data = {
                "analysis_results": analysis_data,
                "generated_at": datetime.now().isoformat(),
                "system_info": {
                    "version": "3.0_search_based",
                    "analysis_type": "business_search_focused"
                }
            }
            
            # JSON文字列として返す（ファイル保存は環境により異なる）
            return filename, save_data
            
        except Exception as e:
            st.warning(f"⚠️ 結果保存エラー: {str(e)}")
            return None, analysis_data

def main():
    st.title("🏢 企業ビジネス分析システム")
    st.markdown("### 企業の事業戦略・競合分析・市場ポジションを自動分析")
    
    # システム情報
    with st.expander("ℹ️ システム情報", expanded=False):
        st.markdown("""
        **分析内容:**
        - 📈 **業界・市場分析**: 所属業界と市場規模・成長性
        - 🏆 **業界内ポジション**: 売上規模・市場シェア・競合比較
        - ⭐ **独自性・差別化**: 技術力・ブランド力・事業モデル
        - 🏗️ **事業ポートフォリオ**: 主力事業・収益構造・事業領域
        
        **特徴:**
        - 🤖 OpenAI GPT-4o-mini による高度なAI分析
        - � SerpAPI検索（オプション：設定時のみ）
        - 🎯 事業分析に特化（EVP分析は廃止）
        - 📝 2400文字の詳細分析（3倍拡張）
        - 📄 JSON形式での結果出力
        - � AI知識ベースによる包括的企業分析
        - 📋 PDF資料対応・多階層クロール（3-4階層）
        - 💾 100,000文字のデータ収集容量
        """)
    
    # APIキー診断
    with st.expander("🔧 APIキー診断", expanded=False):
        if st.button("📋 APIキー設定状況を確認"):
            # OpenAI APIキー確認
            try:
                analyzer = BusinessAnalyzer()
                st.success("✅ OpenAI APIキー: 正常設定済み")
            except:
                st.error("❌ OpenAI APIキー: 未設定または無効")
            
            # SerpAPIキー確認
            test_collector = SearchBasedIRCollector("テスト")
            serpapi_key = test_collector.get_serpapi_key()
            if serpapi_key:
                st.success("✅ SerpAPI キー: 正常設定済み")
                # 簡単なテスト検索
                if st.button("🔍 SerpAPIテスト検索実行"):
                    test_result = test_collector.search_with_serpapi("トヨタ", serpapi_key)
                    if test_result and 'error' not in test_result:
                        st.success("✅ SerpAPI: 検索テスト成功")
                    else:
                        st.error(f"❌ SerpAPI: 検索テスト失敗 - {test_result.get('error', 'Unknown error')}")
            else:
                st.warning("⚠️ SerpAPI キー: 未設定（検索機能は無効化されます）")
    
    # 入力フォーム
    with st.form("analysis_form"):
        company_name = st.text_input(
            "🏢 企業名 *", 
            placeholder="例: トヨタ自動車、ソフトバンク、リクルート",
            help="分析対象の企業名を入力してください（検索ベースでIR情報を自動収集します）"
        )
        
        st.markdown("---")
        submitted = st.form_submit_button("🔍 事業分析開始", type="primary", use_container_width=True)
    
    # 分析実行
    if submitted:
        if not company_name:
            st.error("🚨 企業名は必須入力です。")
            return
        
        analyzer = BusinessAnalyzer()
        
        # プログレスバー
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        status_text.text("🔍 検索ベースでIR情報を収集中...")
        progress_bar.progress(25)
        
        with st.spinner("🤖 AI分析中... (30-60秒程度お待ちください)"):
            progress_bar.progress(50)
            analysis_result = analyzer.analyze_company(company_name)
            progress_bar.progress(80)
        
        if analysis_result:
            # 結果保存
            filename, save_data = analyzer.save_results(company_name, analysis_result)
            progress_bar.progress(100)
            status_text.text("✅ 分析完了！")
            
            # セッション状態に保存
            st.session_state.analysis_results = {
                "data": analysis_result,
                "company_name": company_name,
                "save_data": save_data,
                "filename": filename
            }
        else:
            progress_bar.progress(0)
            status_text.text("❌ 分析に失敗しました")
            st.error("❌ 分析に失敗しました。APIキーまたはネットワーク接続を確認してください。")
    
    # 結果表示
    if 'analysis_results' in st.session_state:
        results = st.session_state.analysis_results
        analysis_data = results["data"]
        company_name = results["company_name"]
        save_data = results["save_data"]
        filename = results["filename"]
        
        st.success("🎉 事業分析が完了しました！")
        
        # 基本情報
        st.markdown("---")
        st.subheader("📊 分析結果サマリー")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("🏢 企業名", company_name)
        with col2:
            st.metric("🎯 分析タイプ", "事業分析特化")
        with col3:
            metadata = analysis_data.get('analysis_metadata', {})
            st.metric("📈 信頼性スコア", f"{metadata.get('reliability_score', 'N/A')}/100")
        
        st.markdown("---")
        
        # タブ形式で結果表示
        tab1, tab2 = st.tabs(["🏆 事業分析結果", "📄 JSON出力"])
        
        with tab1:
            st.subheader("🏆 企業ビジネス分析")
            
            business_data = analysis_data.get('business_analysis', {})
            if business_data:
                # 整形機能を使って美しく表示
                test_collector = SearchBasedIRCollector("display")
                test_collector.display_formatted_analysis(business_data)
            else:
                st.warning("事業分析データが生成されませんでした。")
        
        with tab2:
            st.subheader("📄 JSON形式の分析結果")
            
            # ダウンロードボタン
            json_output = json.dumps(save_data, ensure_ascii=False, indent=2)
            st.download_button(
                label="💾 JSON結果をダウンロード",
                data=json_output,
                file_name=f"business_analysis_{company_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )
            
            # JSON表示
            st.code(json_output, language="json")
        
        # 新しい分析ボタン
        if st.button("🔄 新しい分析を開始"):
            if 'analysis_results' in st.session_state:
                del st.session_state.analysis_results
            st.rerun()

    # フッター
    st.markdown("---")
    st.markdown(
        """
        <div style="text-align: center; color: #666;">
            🔍 企業ビジネス分析システム v3.0 (検索特化版) | Powered by OpenAI GPT-4o-mini + SerpAPI
        </div>
        """, 
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()