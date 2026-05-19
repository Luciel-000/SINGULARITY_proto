============================================================
  SINGULARITY - Chronicle of Origin - スプライト画像ガイド
============================================================

【画像ファイルの置き場所】
  singularity_proto_01/assets/images/ にPNGファイルを置いてください。

【現在対応している画像ファイル】
  player_novice_m.png  ← プレイヤー「ノービス」（男性）
  player_novice_f.png  ← プレイヤー（女性）将来用
  slime_fire.png       ← 火スライム ★ 最初の敵
  slime_water.png      ← 水スライム
  slime_wind.png       ← 風スライム
  slime_earth.png      ← 土スライム
  slime_light.png      ← 光スライム
  slime_dark.png       ← 闇スライム

【画像の推奨仕様】
  形式    : PNG（透過対応 / RGBA）
  サイズ  : 32x32px 〜 128x128px（自動でリサイズされます）
  背景    : 透明（透過PNG）推奨

【画像が読み込めない場合の確認ポイント】
  1. ファイル名のスペルミスがないか確認する
     ○ slime_fire.png
     × SlimeFire.png / slime-fire.png

  2. このフォルダ（assets/images/）に置いてあるか確認する

  3. main.py と同じフォルダから実行しているか確認する
     正しい実行方法:
       cd singularity_proto_01
       python main.py          ← ○ ここで実行
     間違い:
       cd ..
       python singularity_proto_01/main.py   ← × このパスだと画像が見つからない

  4. PNG ファイルが壊れていないか確認する
     別の画像ビューアで開けるか試す

  5. 画像が見つからなくても「図形描画」で動作は続きます
     起動時のコンソールに以下のように表示されます:
       [SpriteManager]  NG: slime_fire.png  (No file found...)  ← 読み込み失敗
       [SpriteManager]  OK: player_novice_m.png               ← 読み込み成功

【将来の画像追加方法】
  1. PNG ファイルをこのフォルダに追加
  2. core/sprite_manager.py の ENEMY_SPRITE_MAP / PLAYER_SPRITE_MAP に追記
     例: "土スライム": "slime_earth",
  3. 再起動すると自動で読み込まれます

============================================================
