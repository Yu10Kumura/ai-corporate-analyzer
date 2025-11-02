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

# ページ設定
st.set_page_config(
    page_title="🏢 企業ビジネス分析システム",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 設定定数
CONFIG = {
    'MAX_CRAWL_DEPTH': 2,
    'DATE_LIMIT_YEARS': 3,
    'MAX_SOURCES': 10,
    'USER_AGENT': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
}

class SearchBasedIRCollector:
    """SerpAPI検索ベースのIR情報収集システム"""
    
    def __init__(self, company_name):
        self.company_name = company_name
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': CONFIG['USER_AGENT']})
    
    def get_serpapi_key(self):
        """SerpAPIキー取得（本番環境対応）"""
        # Streamlit Cloud のSecrets機能を優先
        if hasattr(st, 'secrets') and "SERPAPI_KEY" in st.secrets:
            return st.secrets["SERPAPI_KEY"]
        # 環境変数をフォールバック
        elif os.getenv("SERPAPI_KEY"):
            return os.getenv("SERPAPI_KEY")
        else:
            st.warning("⚠️ SerpAPI キーが設定されていません。IR検索機能は無効化されます。")
            st.markdown("""
            **SerpAPI設定方法（オプション）:**
            - 1. https://serpapi.com でアカウント作成（無料枠月100回）
            - 2. Streamlit Cloud: Secrets機能でSERPAPI_KEYを設定
            - 3. ローカル実行: 環境変数でSERPAPI_KEYを設定
            """)
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
        serpapi_key = self.get_serpapi_key()
        if not serpapi_key:
            st.info("🔍 SerpAPIキーが未設定のため、一般的な公開情報で分析を実行します")
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
            try:
                st.info(f"🔍 検索中: {query}")
                search_results = self.search_with_serpapi(query, serpapi_key)
                
                if search_results and 'organic_results' in search_results:
                    successful_searches += 1
                    for result in search_results['organic_results'][:2]:  # 上位2件のみ
                        url = result.get('link', '')
                        title = result.get('title', '')
                        snippet = result.get('snippet', '')
                        
                        # IR関連URLかチェック
                        if self.is_ir_related_url(url, title):
                            # Webページの内容を取得
                            content = self.fetch_webpage_content(url)
                            if content:
                                collected_data.append({
                                    'url': url,
                                    'content': content[:2000],  # 2000文字まで
                                    'title': title,
                                    'snippet': snippet,
                                    'search_query': query
                                })
                                st.success(f"✅ IR情報を取得: {title}")
                elif search_results and 'error' in search_results:
                    st.warning(f"⚠️ 検索エラー: {search_results.get('error', 'Unknown error')}")
                else:
                    st.debug(f"検索結果なし: {query}")
                
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
        """IR関連URLかどうかを判定"""
        ir_keywords = ['ir', 'investor', '投資家', '決算', '業績', '財務', '有価証券', '年次報告']
        url_lower = url.lower()
        title_lower = title.lower()
        
        return any(keyword in url_lower or keyword in title_lower for keyword in ir_keywords)
    
    def fetch_webpage_content(self, url):
        """Webページの内容を取得"""
        try:
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                text_content = soup.get_text()
                return ' '.join(text_content.split())
            else:
                st.debug(f"HTTP {response.status_code}: {url}")
                return None
        except requests.exceptions.Timeout:
            st.debug(f"タイムアウト: {url}")
            return None
        except requests.exceptions.RequestException as e:
            st.debug(f"取得エラー {url}: {str(e)}")
            return None
        except Exception as e:
            st.debug(f"予期しないエラー {url}: {str(e)}")
            return None

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
                f"【IR情報源】: {item['title']}\n出典URL: {item['url']}\n内容: {item['content'][:800]}...\n"
                for item in ir_data[:3]
            ])
            sources_list = [item['url'] for item in ir_data[:3]]
        
        prompt = f"""
あなたは企業ビジネス分析の専門家です。以下の企業について、事業分析を実行してください。

【分析対象企業】: {company_name}

【利用可能な情報】:
{ir_content if ir_content else "一般的な公開情報に基づく分析を実行"}

【重要制約】:
1. 事業分析の4項目のみに特化
2. 推測の場合は明確に「推定」と記載
3. データがない場合は「情報不足」と明記
4. 情報源がある場合は具体的なURL出典を明記
5. 各分析は800文字程度で詳細に記述

【分析項目】:
1. industry_market: 業界・市場分析（所属業界、市場規模、成長性）
2. market_position: 業界内ポジション（売上規模、市場シェア、競合比較）
3. differentiation: 独自性・差別化要因（技術力、ブランド力、事業モデル）
4. business_portfolio: 事業ポートフォリオ分析（主力事業、収益構造、事業領域）

【出力形式】:
以下のJSON形式で回答してください：

{{
  "business_analysis": {{
    "industry_market": "詳細な業界・市場分析（800文字程度）",
    "market_position": "業界内ポジションの分析（800文字程度）", 
    "differentiation": "独自性・差別化要因の分析（800文字程度）",
    "business_portfolio": "事業ポートフォリオの分析（800文字程度）"
  }},
  "analysis_metadata": {{
    "company_name": "{company_name}",
    "analysis_date": "{datetime.now().strftime('%Y-%m-%d')}",
    "data_sources": {sources_list if sources_list else ["一般的な公開情報"]},
    "ir_sources_count": {len(sources_list) if sources_list else 0},
    "reliability_score": {90 if sources_list else 70}
  }}
}}
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
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=4000
            )
            
            result_text = response.choices[0].message.content
            
            # JSON解析
            try:
                # JSON部分を抽出
                json_start = result_text.find('{')
                json_end = result_text.rfind('}') + 1
                json_text = result_text[json_start:json_end]
                
                result = json.loads(json_text)
                return result
                
            except json.JSONDecodeError:
                st.error("❌ AI応答のJSON解析に失敗しました")
                st.code(result_text)
                return None
                
        except Exception as e:
            st.error(f"❌ AI分析エラー: {str(e)}")
            return None
    
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
        - 🔍 SerpAPI検索ベースのIR情報自動収集
        - 📊 IR資料・決算情報・有価証券報告書を自動検索
        - 🎯 事業分析に特化（EVP分析は廃止）
        - 📝 800文字の詳細分析
        - 📄 JSON形式での結果出力
        - 🔗 収集した情報源のURL出典明記
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
            
            business_labels = {
                "industry_market": "📈 業界・市場分析",
                "market_position": "🏆 業界内ポジション",
                "differentiation": "⭐ 独自性・差別化要因",
                "business_portfolio": "🏗️ 事業ポートフォリオ分析"
            }
            
            business_data = analysis_data.get('business_analysis', {})
            if business_data:
                for key, label in business_labels.items():
                    with st.expander(label, expanded=True):
                        content = business_data.get(key, "分析データが不足しています")
                        st.write(content)
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