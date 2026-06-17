# SINGULARITY - Chronicle of Origin -

Pythonで開発中のオリジナルRPGプロトタイプです。

## 概要

「プレイヤーの行動で世界が変化するRPG」をテーマに制作中。

属性・ジョブ進化・観測補助機構システムなどを実装予定です。

現在はプロトタイプ段階として、

* 戦闘システム
* プレイヤー管理
* 敵管理
* ワールド管理
* スプライト管理

などの基礎システムを構築しています。

---

## 使用技術

* Python
* pygame
* Git / GitHub

---

## 起動方法

```bash
pip install pygame
python main.py
```

---

## 現在の実装内容

* プレイヤー表示
* 敵表示
* 戦闘基礎システム
* スプライト管理
* 日本語フォント対応
* モジュール分割構成

---

## 今後の実装予定

* 属性システム
* ジョブ進化
* プレイヤー補助システム
* マップ移動
* セーブ機能
* UI改善
* ドットアニメーション

---

## コンセプト

「プレイヤーの記憶に残るゲーム体験」を目標に制作しています。

ダークファンタジー × 成長 × 選択 をテーマに、
独自の世界観を構築中です。

---

## Author

LUCIEL_000

---

## Prototype 0.8 - Action Log & Job Unlock System

### 実装内容

- 行動ログシステムを追加
- 通常攻撃、スキル使用、観察、逃走、勝利、敗北、ジョブチェンジを記録
- 行動ログからジョブ解放候補を判定
- `fighter` / `mage` の解放条件を追加
- `player.unlocked_jobs` に解放済みジョブを保持
- 解放済みジョブのみジョブメニューで選択可能
- `DEBUG_MODE = True` では開発用に全ジョブ選択可能
- ジョブ解放時にメッセージ表示
- DEBUG用の行動ログオーバーレイを追加
- `DEBUG_MODE = False` の本編想定テスト完了

### 最新コミット

- Step6: 15a6661

### 注意事項

- 自動転職はまだ行わない（プレイヤーがジョブメニューで選んだ時のみ転職）
- `DEBUG_MODE` は開発用チート管理のためのフラグ

### 次の予定

- Prototype 0.9: セーブ/ロードの土台を検討

---

## Prototype 0.9 - Save & Load System

### 実装済み

- セーブ/ロード機能の土台を追加
- `save_system.py` を追加
- JSON形式でセーブデータを保存
- `current_job_id` を保存/ロード
- `unlocked_jobs` を保存/ロード
- `action_log` を保存/ロード
- player位置を保存/ロード
- 現在zoneを保存/ロード
- `save_data/` を `.gitignore` に追加
- `DEBUG_MODE=True` の開発用として F5 セーブ / F9 ロードを追加
- タイトル画面で L キーからロードできるようにした
- 探索中に Esc で SAVE / LOAD メニューを開けるようにした
- SAVE / LOAD / CANCEL を選択できるようにした
- ↑ / ↓ で選択、Z / Enter で決定、Esc / X で閉じる
- セーブスロット概要として保存時刻、Zone、Job、version を表示
- `save_system.py` に `saved_at` を保存
- UI表示用の `get_save_info()` を追加
- プレイヤーの基本ステータスをセーブ/ロード対象に追加
- level を保存/ロード
- exp を保存/ロード
- hp / max_hp を保存/ロード
- atk / defense を保存/ロード
- magic_attack / magic_defense を保存/ロード
- 古いセーブデータに status が無くても落ちないようにした
- hp が 0 未満や max_hp 超えにならないよう補正
- ストーリー進行フラグ保存の土台を追加
- seen_events を保存/ロード
- completed_events を保存/ロード
- story_flags を保存/ロード
- prologue_intro / sage_boot / NPC会話ID の最低限の記録に対応
- elder_first 完了時に first_elder_talk / met_elder を記録
- sage_boot 完了時に sage_booted を記録
- 古いセーブデータに story が無くても落ちないようにした

### Final Check

- main.py 起動確認 OK
- タイトル画面確認 OK
- NEW GAME 確認 OK
- LOAD GAME がセーブなしでも落ちないことを確認
- プロローグ開始確認 OK
- 町/探索状態への遷移確認 OK

### 最新コミット

- Step1: b4cab11
- ignore save_data: 6caa42c
- Step2: fa085c5
- Step3: d31dfb9
- Step4: 4212619
- Step5: 89d9953
- Step6: 099916a

### 注意事項

- 本格的なクエスト管理はまだ未実装
- 複雑な分岐管理はまだ未実装
- 複数セーブスロットはまだ未実装
- 本格的なセーブ画面デザインは今後調整
- F5/F9 は開発用
- 次は Prototype 1.0 に向けた整理を検討

---

## Prototype 1.0 - Stable Start Flow

### Step1

- タイトル画面に選択式メニューを追加
- NEW GAME / LOAD GAME / QUIT を表示
- ↑ / ↓ または W / S で選択
- Z / Enter / Space で決定
- NEW GAME は既存のプロローグ開始フローへ接続
- LOAD GAME は既存ロード処理へ接続
- セーブデータなしでも落ちずにタイトルへ留まる
- QUIT でゲーム終了できるようにした
- 既存の Lキー直接ロードは維持

### Step2

- NEW GAME 後の prologue_intro 文面を調整
- 「名もなき祈り」
- 「世界の叡智」
- 「未完成の観測補助機構」へ自然につながる導入にした
- prologue_intro → sage_boot → 探索 の既存フローは維持
- story_flags の prologue_intro / sage_boot 記録が壊れていないことを確認
- 旧称表記が出ていないことを確認

### Step3

- Player に support_system_name を追加
- デフォルト名は「観測補助機構」
- support_system_name をセーブ/ロード対象に追加
- 古いセーブデータや空文字でも「観測補助機構」にフォールバック
- Game に get_support_system_display_name() を追加
- sage_boot 開始時の話者名に表示名ヘルパーを使用
- DEBUG_MODE=True のとき F6 で仮に「ルシエル」へ変更できるようにした
- 本格的な名前入力UIはまだ未実装

### Step4

- 観測補助機構の名前入力UIを追加
- sage_boot 完了後に名前入力画面へ進む
- 入力後に探索へ進む流れに変更
- 空入力時は「観測補助機構」にフォールバック
- 最大12文字まで入力可能
- Backspace で削除
- Enter / Z で決定
- Esc でキャンセルし「観測補助機構」に決定
- 入力した名前は support_system_name に保存される
- SAVE / LOAD で名前が復元される
- LOAD GAME では名前入力画面に行かない
- DEBUG F6 の仮変更機能は維持

### Final Check

- 構文チェック OK
- main.py 起動確認 OK
- タイトルメニュー NEW GAME / LOAD GAME / QUIT OK
- NEW GAME → prologue_intro → sage_boot → 名前入力 → 探索 の流れ OK
- 観測補助機構の名前入力 OK
- 空入力時の「観測補助機構」フォールバック OK
- support_system_name の SAVE / LOAD 復元 OK
- LOAD GAME では名前入力画面に戻らないことを確認
- story_flags の prologue_intro / sage_boot 記録 OK
- DEBUG F6 / F5 / F9 OK
- 探索・NPC会話・戦闘開始に影響なし
- save_data やテスト用スクリプトは commit 対象外
- Prototype 1.0 完了

### 最新コミット

- Step1: 43e48fa
- Step2: fa53e87
- Step3: bb130a0
- Step4: b47ce55
- Step4 docs: 1bd1a93
