# チーム登録用ディスクリプション

選択チャレンジ: Field Shift
対象地域: 日本（関東地方南部＝茨城・千葉を中心に）

## 日本語版

友人の米農家が、台風と大雨で稲が倒れる「倒伏」の被害を受けたことがきっかけです。農家は台風の警報が出ると、まだ実りきっていなくても安全側で早めに刈り取ります。しかし、そのうち実際に被害が出る台風は一部で、早刈りは収量と品質を捨てる判断でもあります。「待つか、刈るか」を決める客観的な材料が、現場にはほとんどありません。

私たちは、NASA の地球観測・予報データ（GPM IMERG、GEOS-FP、POWER）と、農水省の被害統計、農家の知見を組み合わせて、次の 3 つに取り組みます。

1. 台風・大雨の予報が出たとき、稲が倒れる条件（雨量と、稲の実り具合＝出穂後の積算気温）に当たるかを判定する、軽量なモデルを作る。農家の判断を置き換えるのではなく、「刈る／待ってよい」の材料を出す。
2. 過去の台風で検証し、被害が出る台風を見逃さずに、しなくてよい早刈りをどれだけ減らせるかを、限界（台風の数が少ない、統計が風水害の合計であること）も含めて正直に示す。
3. 予測と結果の履歴を蓄積し、品種・田植え日・輪作といった作付計画の意思決定支援へ広げる道筋を示す。

NASA のデータは学習にも使い、GPU のない普通のパソコンで動く軽さを保ちます。まず収穫判断を支援する土台を作り、将来の作付計画の比較につなげることを目指します。

## English version

Our project started with a friend who farms rice in Japan and lost part of a crop to lodging, where rice plants are flattened by typhoon wind and heavy rain. When a typhoon warning is issued, farmers usually harvest early to be safe, even before the crop is fully ripe. But only some of those typhoons actually cause damage, and harvesting early gives up yield and quality. Farmers have almost no objective evidence to decide whether to wait or to harvest.

Combining NASA Earth observation and forecast data (GPM IMERG, GEOS-FP, POWER) with damage statistics from Japan's Ministry of Agriculture and farmers' local knowledge, we will do three things:

1. Build a lightweight model that tells, when a typhoon or heavy rain is forecast, whether conditions match those under which rice lodges (rainfall and crop ripeness, measured as accumulated temperature after heading). It does not replace the farmer's judgment; it provides evidence for "harvest now" or "safe to wait."
2. Test it on past typhoons and show honestly how many unnecessary early harvests it could have avoided without missing damaging storms, including its limits (few typhoons, and statistics that combine wind and flood damage).
3. Accumulate a history of predictions and outcomes, and outline how it can grow into decision support for crop planning: variety, planting date, and rotation.

NASA data is used for training, and the model is light enough to run on an ordinary computer without a GPU. We start with a foundation for harvest decisions and aim to extend it to comparing planting strategies in the future.
