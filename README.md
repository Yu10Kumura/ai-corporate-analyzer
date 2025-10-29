# 🏢 AI企業分析システム

企業のEVP（Employee Value Proposition）とビジネス分析を自動化するAIシステムです。

## 🎯 概要

このシステムは、ユーザーが基本的な企業情報を入力するだけで、LLMが自動でEVP・ビジネス分析を実施し、構造化された詳細レポートを生成します。

## 📋 主要機能

### 🔍 EVP分析（5項目）
- **💰 Rewards** - 報酬・待遇
- **🚀 Opportunity** - 機会・成長  
- **🏢 Organization** - 組織・企業文化
- **👥 People** - 人材・マネジメント
- **💼 Work** - 働き方・業務

### 📊 ビジネス分析（4項目）
- **📈 業界・市場分析** - 所属業界と将来性
- **🏆 業界内ポジション** - 売上・利益の位置付けと期待値
- **⭐ 独自性・差別化要因** - オリジナリティと競合優位性
- **🏗️ 事業ポートフォリオ分析** - 主要事業と収益構成

## 🚀 ライブデモ

**URL**: https://ai-corporate-analyzer.streamlit.app *(デプロイ後に更新)*

## 💻 ローカル実行

### 1. 環境準備
```bash
# リポジトリクローン
git clone https://github.com/Yu10Kumura/ai-corporate-analyzer.git
cd ai-corporate-analyzer

# 仮想環境作成・有効化
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 依存関係インストール
pip install -r requirements.txt
```

### 2. 環境変数設定
```bash
# .envファイル作成
echo "OPENAI_API_KEY=your_api_key_here" > .env
echo "SERPAPI_KEY=your_serpapi_key_here" >> .env  # オプション
```

**環境変数説明:**
- `OPENAI_API_KEY`: OpenAI APIキー（必須）
- `SERPAPI_KEY`: SerpAPI APIキー（オプション - 外部情報収集用）

**SerpAPI設定（オプション）:**
1. [SerpAPI](https://serpapi.com/)でアカウント作成
2. 無料枠で月100回検索利用可能
3. ダッシュボードからAPIキーを取得
4. 未設定でもフォールバック機能で動作

**SerpAPIキー取得手順:**
1. https://serpapi.com/ にアクセス
2. 「Sign Up」でアカウント作成
3. ダッシュボードの「API Key」をコピー
4. 環境変数 `SERPAPI_KEY` に設定

### 3. アプリ起動
```bash
streamlit run streamlit_app.py
```

## ⚙️ 本番環境設定

### Streamlit Cloud デプロイ

1. **GitHubリポジトリ**をStreamlit Cloudに接続
2. **Secrets設定**でAPIキーを追加：
   ```toml
   [secrets]
   OPENAI_API_KEY = "sk-proj-..."
   SERPAPI_KEY = "your_serpapi_key_here"  # オプション
   ```
3. **自動デプロイ**でアプリが公開されます

**注意**: SerpAPIキーを設定しない場合、外部情報収集はスキップされ、フォールバック分析が使用されます。

## 📁 ファイル構成

```
ai-corporate-analyzer/
├── streamlit_app.py         # メインアプリケーション
├── requirements.txt         # Python依存関係
├── .gitignore              # Git除外設定
├── .streamlit/
│   └── config.toml         # Streamlit設定
└── README.md               # このファイル
```

## 🔧 技術スタック

- **Python 3.8+**
- **Streamlit** - WebUIフレームワーク
- **OpenAI GPT-4o-mini** - AI分析エンジン
- **JSON** - 構造化出力形式

## 📝 使用方法

### 入力
1. **企業名** (必須) - 分析対象企業
2. **ホームページURL** (任意) - より詳細な分析が可能
3. **分析重点分野** (必須) - 新卒採用、エンジニア採用等

### 出力
- **詳細レポート** - EVP・ビジネス分析各項目
- **JSON形式** - 他システムでの活用可能
- **ダウンロード機能** - 結果の保存・共有

## 🎨 画面構成

- **📈 EVP分析タブ** - 5項目の詳細分析
- **🏆 ビジネス分析タブ** - 4項目の企業分析  
- **📄 JSON出力タブ** - 結果のダウンロード

## ⚠️ 注意事項

- OpenAI APIキーが必要です
- 分析結果は公開情報に基づいた推定を含みます
- 1回の分析で約30-60秒程度かかります

## 🔒 セキュリティ

- API キーは環境変数またはSecrets機能で管理
- `.gitignore`でconfig.envを除外
- HTTPS通信で安全な接続

## 📈 今後の改善予定

- [ ] Web検索による最新情報収集
- [ ] 競合企業との比較分析
- [ ] PDF出力機能
- [ ] 分析履歴の管理

## 🤝 コントリビューション

プルリクエストやイシューは歓迎します。

## 📄 ライセンス

MIT License

---

**開発者**: Yu10Kumura  
**作成日**: 2025年10月28日  
**バージョン**: 1.0.0