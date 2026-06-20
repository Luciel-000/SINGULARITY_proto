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

---

## Prototype 1.1 - Cleanup / Naming Polish

### Step1

- 旧称「大賢者」表記を整理
- README / コメント / 説明文の表記を「観測補助機構」系へ統一
- 大賢者システム → 観測補助機構システム
- 大賢者メッセージ → 観測補助メッセージ
- スキル説明文の旧称も整理
- Select-String で「大賢者」0件を確認
- 機能変更なし
- save_data やテスト用スクリプトは commit 対象外

### Step2

- 観測補助機構の表示名を戦闘ログへ反映
- 戦闘ログの観測補助メッセージ接頭辞を player.support_system_name 由来の名前に差し替え
- 名前入力で設定した名前が戦闘中にも表示される
- 空文字 / None / 不正値の場合は「観測補助機構」にフォールバック
- 戦闘開始メッセージにも同じ差し替え処理を適用
- 戦闘バランスや処理ロジックは変更なし
- core/*.py に「大賢者」表記が残っていないことを確認

### 最新コミット

- Step1: e4bd386
- Step2: 7dd8216

### Final Check

- 構文チェック OK
- core/*.py に「大賢者」表記が残っていないことを確認
- デフォルト名では戦闘ログが《観測補助機構》になることを確認
- 名前変更時は戦闘ログが《ルシエル》などの設定名になることを確認
- 空文字 / None は《観測補助機構》にフォールバック
- support_system_name の SAVE / LOAD 復元 OK
- LOAD GAME では名前入力画面に戻らないことを確認
- NEW GAME → prologue_intro → sage_boot → 名前入力 → 探索 OK
- 通常攻撃 / スキル / 観察 / 勝利 / 敗北 / 逃走 / action_log OK
- NPC会話 OK
- DEBUG F6 / F5 / F9 OK
- save_data やテスト用スクリプトは commit 対象外
- Prototype 1.1 完了

### 最新コミット

- Step2 docs: fb93e08

---

## Prototype 1.2 - Story Progression / NPC Dialogue

### Step1

- NPC会話の条件分岐土台を追加
- 謎の老人の会話IDを進行状況で切り替え
- battle_win_count >= 1 の場合は elder_after_battle を優先
- sage_booted が True の場合は elder_after_sage を使用
- 条件なしの場合は elder_first を使用
- elder_after_sage / elder_after_battle の会話を追加
- story_flags / action_log の保存・復元後も会話分岐が維持されることを確認
- core/*.py に「大賢者」表記が残っていないことを確認
- save_data やテスト用スクリプトは commit 対象外

### Step2

- 簡易クエスト用 story_flags を追加
- elder_first 完了後に quest_check_field=True を設定
- sage_booted 後の老人会話でも必要に応じて quest_check_field=True を設定
- 戦闘勝利後に quest_check_field_done=True を設定
- quest_check_field_done=True の場合は elder_after_quest_done を優先
- elder_after_quest_done の会話を追加
- SAVE / LOAD 後も quest_check_field / quest_check_field_done が復元されることを確認
- core/*.py に「大賢者」表記が残っていないことを確認
- クエスト一覧UIや報酬処理はまだ未実装
- save_data やテスト用スクリプトは commit 対象外

### Step3

- 現在の目的表示を追加
- get_current_objective_text() を追加
- quest_check_field=True の場合は「目的：村の外を確認する」を表示
- quest_check_field_done=True の場合は「目的：老人に報告する」を表示
- フラグなしの場合は目的表示なし
- 探索中 STATE_PLAY のみ右上に目的を1行表示
- 戦闘中・会話中には表示しない
- SAVE / LOAD 後も目的表示が復元されることを確認
- core/*.py に「大賢者」表記が残っていないことを確認
- クエスト一覧UIや報酬処理はまだ未実装
- save_data やテスト用スクリプトは commit 対象外

### Final Check

- 構文チェック OK
- NPC会話分岐 OK
- elder_first / elder_after_sage / elder_after_battle / elder_after_quest_done の分岐確認 OK
- elder_first 後に quest_check_field=True を確認
- 戦闘勝利後に quest_check_field_done=True を確認
- SAVE / LOAD 後も story_flags / action_log が復元されることを確認
- 現在の目的表示 OK
- quest_check_field=True で「目的：村の外を確認する」
- quest_check_field_done=True で「目的：老人に報告する」
- フラグなしでは目的表示なし
- 探索中 STATE_PLAY のみ目的表示
- 戦闘中・会話中には目的表示なし
- support_system_name の保存・復元 OK
- 戦闘ログ名反映 OK
- core/*.py に「大賢者」表記が残っていないことを確認
- save_data やテスト用スクリプトは commit 対象外
- Prototype 1.2 完了

### 最新コミット

- Step1: 0162cd7
- Step2: bb58527
- Step3: b63ae9e
- Step3 docs: caddc50

---

## Prototype 1.3 - Quest Completion / Progression Unlock

### Step1

- 老人への報告で最初の簡易クエストを完了できるようにした
- quest_check_field_done=True の状態で elder_after_quest_done を完了すると quest_check_field_reported=True を設定
- quest_check_field_reported=True の場合は目的表示を消す
- 報告後の老人会話 elder_after_report を追加
- SAVE / LOAD 後も quest_check_field_reported が復元されることを確認
- core/*.py に「大賢者」表記が残っていないことを確認
- 報酬UI / アイテム報酬 / クエスト一覧UI はまだ未実装
- save_data やテスト用スクリプトは commit 対象外

### Step2

- クエスト報告後の次目的フラグを追加
- elder_after_quest_done 完了時に quest_go_north=True を設定
- quest_go_north=True の場合は「目的：村の北へ向かう」を表示
- quest_go_north は quest_check_field_reported より優先表示
- elder_after_report の会話に北へ向かう示唆を追加
- SAVE / LOAD 後も quest_go_north が復元されることを確認
- core/*.py に「大賢者」表記が残っていないことを確認
- 新マップ / 北の祠イベント / クエスト一覧UI / 報酬UI はまだ未実装
- save_data やテスト用スクリプトは commit 対象外

### Step3

- 村の北へ向かう目的に位置ベースの進行判定を追加
- town 内で quest_go_north=True の状態で北側しきい値へ入ると quest_go_north_reached=True を設定
- quest_go_north_reached=True の場合は「目的：北の異変を調べる」を表示
- elder_after_go_north_reached の会話を追加
- SAVE / LOAD 後も quest_go_north_reached が復元されることを確認
- core/*.py に「大賢者」表記が残っていないことを確認
- 新マップ・北の祠イベント・報酬UIはまだ未実装
- save_data やテスト用スクリプトは commit 対象外

### Step4

- 新しい zone「north_road（北の道）」を追加
- ルミナ村北側から北の道へ移動できるようにした
- quest_go_north_reached=True のときだけ北出口から north_road へ遷移
- 未達成時は「まだ北へ進む理由がないようだ」と表示して遷移しない
- north_road は古い祠へ続く道の入口として配置
- north_road から town へ戻れる
- north_road は敵なしの小規模固定マップ
- north_road で SAVE / LOAD 後も復帰できることを確認
- 既存 town ↔ field 遷移を維持
- core/*.py に「大賢者」表記が残っていないことを確認
- 北の祠イベント・敵配置・報酬UIはまだ未実装
- save_data やテスト用スクリプトは commit 対象外

### Step5

- north_road 北側に古い祠の入口イベント地点を追加
- 初回到達時に shrine_anomaly_seen=True を設定
- 北の空気の重さ、祈りの気配、封じられた祠の演出を追加
- 観測補助機構の設定名を話者名として使用
- イベント後の目的を「目的：古い祠の封印を調べる」に更新
- shrine_anomaly_seen=True 後は同じイベントが再発しない
- SAVE / LOAD 後も shrine_anomaly_seen が復元されることを確認
- north_road と town の往復を維持
- 祠内部マップ・ボス戦・報酬はまだ未実装
- save_data やテスト用スクリプトは commit 対象外

### Step6

- 古い祠の異変を見た後、老人から封印に関する手がかりを得る進行を追加
- shrine_anomaly_seen=True かつ shrine_hint_received=False の場合は「目的：老人に祠のことを尋ねる」を表示
- elder_after_shrine_anomaly の会話を追加
- elder_after_shrine_anomaly 完了時に shrine_hint_received=True を設定
- shrine_hint_received=True の場合は「目的：封印の欠片を探す」を表示
- elder_after_shrine_hint の会話を追加
- 老人は封印や欠片について答えを言い切らず、ヒント中心にする
- SAVE / LOAD 後も shrine_hint_received が復元されることを確認
- core/*.py に「大賢者」表記が残っていないことを確認
- 封印の欠片取得・祠内部マップ・封印解除はまだ未実装
- save_data やテスト用スクリプトは commit 対象外

### Step7

- field に最初の封印の欠片イベント地点を追加
- shrine_hint_received=True かつ shrine_fragment_1_obtained=False の時だけ欠片を表示
- 欠片付近でZを押すと shrine_fragment_1_found イベントを開始
- 取得時に shrine_fragment_1_seen=True / shrine_fragment_1_obtained=True を設定
- 取得後の目的を「目的：古い祠へ戻る」に更新
- 取得済みの欠片は非表示となり、再取得できない
- 観測補助機構の設定名を欠片イベントの話者名に使用
- SAVE / LOAD 後も shrine_fragment_1_obtained が復元されることを確認
- core/*.py に「大賢者」表記が残っていないことを確認
- 祠で欠片を使う処理・封印解除・祠内部マップ・ボス戦はまだ未実装
- save_data やテスト用スクリプトは commit 対象外

### Step8

- 最初の封印の欠片を取得後、north_road 北側の古い祠でZを押す進行を追加
- shrine_fragment_1_obtained=True かつ shrine_fragment_1_offered=False の時だけ封印反応イベントを開始
- イベント時に shrine_fragment_1_offered=True / shrine_seal_reacted=True を設定
- 欠片をかざすと封印の紋様へ光が流れ、祠の奥へ続く道がわずかに開く演出を追加
- 観測補助機構の設定名をイベント話者名に使用
- shrine_seal_reacted=True の場合は「目的：祠の奥へ進む」を表示
- 祠入口の見た目を、封印反応後に変化させる
- 再度Zを押してもイベントは再発せず、「封印はわずかに開いている」などの短い反応のみ
- SAVE / LOAD 後も shrine_fragment_1_offered / shrine_seal_reacted が復元されることを確認
- core/*.py に「大賢者」表記が残っていないことを確認
- 祠内部マップ・実際の遷移・ボス戦・封印の完全解除はまだ未実装
- save_data やテスト用スクリプトは commit 対象外

### Step9

- 新ゾーン shrine_inner を追加
- 表示名を「古い祠・内部」に設定
- 敵が出現しない小規模固定マップを追加
- 石壁・石床・柱・祭壇地点を配置
- shrine_seal_reacted=True の時だけ north_road の祠入口から入場可能
- shrine_inner の出口から north_road へ戻れる
- 初回入場時に shrine_inner_entered=True を設定
- 初回のみ shrine_inner_arrival イベントを表示
- 観測補助機構の設定名を初回入場イベントの話者名に使用
- shrine_inner_entered=True かつ shrine_altar_investigated=False の場合は「目的：祠の祭壇を調べる」を表示
- SAVE / LOAD 後も current_zone_id と shrine_inner_entered が復元されることを確認
- core/*.py に「大賢者」表記が残っていないことを確認
- 祭壇を調べる本イベント・ボス戦・封印の完全解除はまだ未実装
- save_data やテスト用スクリプトは commit 対象外

### 最新コミット

- Step1: b6357e2
- Step2: a395398
- Step3: 5e2844b
- Step4: 244feac
- Step5: 78d07ce
- Step6: 0e5c2b6
- Step7: 8b57ca4
- Step8: 30350dd
- Step9: a31b155
