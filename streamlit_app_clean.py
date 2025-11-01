#!/usr/bin/env python3
"""
🏢 企業ビジネス分析システム - Streamlit Web版
EVP機能を削除し、企業のビジネス分析に特化したAIシステム
"""

import streamlit as st
import os
import json
import datetime
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

class IRDataCollector:
    """IR情報収集システム（簡素化版）"""
    
    def __init__(self, company_domain):
        self.company_domain = company_domain
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': CONFIG['USER_AGENT']})
    
    def collect_basic_ir_info(self):
        """基本的なIR情報を収集"""
        try:
            ir_patterns = [
                f"https://{self.company_domain}/ir/",
                f"https://{self.company_domain}/investor/",
                f"https://ir.{self.company_domain}/"
            ]
            
            collected_data = []
            
            for url in ir_patterns:
                try:
                    st.info(f"🔍 IR情報を探索中: {url}")
                    response = self.session.get(url, timeout=10)
                    
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.text, 'html.parser')
                        content = response.text[:2000]  # 最初の2000文字
                        
                        collected_data.append({
                            'url': url,
                            'content': content,
                            'title': soup.title.string if soup.title else f"IR情報 - {self.company_domain}"
                        })
                        
                        st.success(f"✅ IR情報を取得: {url}")
                        break  # 1つ成功したら終了
                        
                except requests.exceptions.RequestException:
                    continue
            
            return collected_data
            
        except Exception as e:
            st.warning(f"⚠️ IR情報の収集中にエラー: {str(e)}")
            return []

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
        if ir_data:
            ir_content = "\n".join([
                f"【IR情報】: {item['title']}\n内容: {item['content'][:800]}...\n"
                for item in ir_data[:3]
            ])
        
        prompt = f"""
あなたは企業ビジネス分析の専門家です。以下の企業について、事業分析のみを実行してください。

【分析対象企業】: {company_name}

【利用可能な情報】:
{ir_content if ir_content else "公開情報に基づく分析を実行"}

【重要制約】:
1. EVP分析は実行しない
2. 事業分析の4項目のみに特化
3. 推測の場合は明確に「推定」と記載
4. データがない場合は「情報不足」と明記
5. 出典がある場合は必ず明記

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
    "data_sources": ["企業公式情報", "IR開示資料"],
    "reliability_score": 85
  }}
}}
"""
        return prompt
    
    def analyze_company(self, company_name, company_url=None):
        """企業の事業分析を実行"""
        
        # IR情報収集
        ir_data = []
        if company_url:
            domain = self._extract_domain(company_url)
            if domain:
                collector = IRDataCollector(domain)
                ir_data = collector.collect_basic_ir_info()
        
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
    
    def _extract_domain(self, url):
        """URLからドメインを抽出"""
        try:
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            
            parsed = urlparse(url)
            domain = parsed.netloc
            if domain.startswith('www.'):
                domain = domain[4:]
            return domain
        except:
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
                    "version": "2.0_business_focused",
                    "analysis_type": "business_only"
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
        - EVP分析を廃止し、事業分析に特化
        - IR情報に基づく客観的分析
        - 800文字の詳細分析
        - JSON形式での結果出力
        """)
    
    # 入力フォーム
    with st.form("analysis_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            company_name = st.text_input(
                "🏢 企業名 *", 
                placeholder="例: トヨタ自動車、ソフトバンク、リクルート",
                help="分析対象の企業名を入力してください"
            )
        
        with col2:
            company_url = st.text_input(
                "🌐 企業URL（任意）",
                placeholder="https://www.company.co.jp",
                help="より詳細な分析のために企業URLを入力（任意）"
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
        
        status_text.text("🔍 企業情報を収集中...")
        progress_bar.progress(25)
        
        with st.spinner("🤖 AI分析中... (30-60秒程度お待ちください)"):
            progress_bar.progress(50)
            analysis_result = analyzer.analyze_company(company_name, company_url)
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
            📊 企業ビジネス分析システム v2.0 | Powered by OpenAI GPT-4o-mini
        </div>
        """, 
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()