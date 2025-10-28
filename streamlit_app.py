#!/usr/bin/env python3
"""
企業EVP・企業分析システム - Streamlit Web版（本番環境対応）
"""

import streamlit as st
import os
import json
import datetime
from pathlib import Path
from openai import OpenAI

# ページ設定
st.set_page_config(
    page_title="🏢 AI企業分析システム",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed"
)

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
        """LLMに企業調査を依頼"""
        prompt = self.create_research_prompt(company_info)
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "企業リサーチの専門家として、正確で具体的な情報をJSON形式で回答してください。"},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=6000,  # 詳細な分析のためトークン数を増加
                temperature=0.3
            )
            
            content = response.choices[0].message.content.strip()
            
            # JSONデータを抽出
            if "```json" in content:
                json_start = content.find("```json") + 7
                json_end = content.find("```", json_start)
                json_content = content[json_start:json_end].strip()
            else:
                json_content = content
            
            return json.loads(json_content)
            
        except Exception as e:
            st.error(f"AI調査中にエラーが発生しました: {e}")
            return None
    
    def save_results(self, company_info, research_data):
        """結果をJSONファイルに保存"""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"research_{company_info['company_name']}_{timestamp}.json"
        filepath = self.results_dir / filename
        
        save_data = {
            "company_info": company_info,
            "research_results": research_data,
            "generated_at": datetime.datetime.now().isoformat()
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
                "🌐 ホームページURL（任意）", 
                placeholder="例: https://www.company.co.jp/",
                help="企業の公式サイトURL（より詳細な分析が可能）"
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
        
        st.markdown("---")
        submitted = st.form_submit_button("🔍 AI分析開始", type="primary", use_container_width=True)
    
    # フォーム送信時の処理
    if submitted:
        if not company_name or not focus_area:
            st.error("🚨 企業名と分析重点分野は必須入力です。")
            return
        
        # 会社情報の準備
        company_info = {
            "company_name": company_name,
            "website_url": website_url,
            "focus_area": focus_area,
            "analysis_level": analysis_level,
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        # 調査実行
        researcher = StreamlitCompanyResearcher()
        
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
            
            # 結果表示
            st.success("🎉 AI分析が完了しました！")
            
            # 基本情報表示
            st.markdown("---")
            st.subheader("📊 分析結果サマリー")
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("🏢 企業名", company_name)
            with col2:
                st.metric("🎯 重点分野", focus_area)
            with col3:
                st.metric("📊 分析レベル", analysis_level)
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
                
                for key, label in evp_labels.items():
                    with st.expander(label, expanded=True):
                        st.write(research_data['evp'][key])
            
            with tab2:
                st.subheader("🏆 ビジネス分析")
                
                business_labels = {
                    "industry_market": "📈 業界・市場分析",
                    "market_position": "🏆 業界内ポジション",
                    "differentiation": "⭐ 独自性・差別化要因",
                    "business_portfolio": "🏗️ 事業ポートフォリオ分析"
                }
                
                for key, label in business_labels.items():
                    with st.expander(label, expanded=True):
                        st.write(research_data['business_analysis'][key])
            
            with tab3:
                st.subheader("📄 JSON形式の分析結果")
                st.markdown("分析結果をJSON形式で表示します。コピーして他のシステムでも活用できます。")
                
                # ダウンロードボタン
                json_output = json.dumps(save_data, ensure_ascii=False, indent=2)
                st.download_button(
                    label="💾 JSON結果をダウンロード",
                    data=json_output,
                    file_name=f"research_{company_name}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json"
                )
                
                # JSON表示
                st.code(json_output, language="json")
                
                if filepath:
                    st.info(f"💾 結果はサーバーにも保存されました: {filepath}")
        
        else:
            progress_bar.progress(0)
            status_text.text("❌ 分析に失敗しました")
            st.error("❌ AI分析に失敗しました。APIキーの設定またはネットワーク接続を確認してください。")

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