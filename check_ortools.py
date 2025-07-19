import ortools.graph.python.min_cost_flow as min_cost_flow

try:
    # SimpleMinCostFlow のインスタンスを作成
    smcf = min_cost_flow.SimpleMinCostFlow()

    # インスタンスのすべての属性とメソッドを表示
    print("SimpleMinCostFlow オブジェクトの属性とメソッド:")
    for attr in sorted(dir(smcf)):
        print(f"- {attr}")

    # 特に AddArcs があるかチェック
    if hasattr(smcf, 'AddArcs'):
        print("\n✅ 'AddArcs' メソッドが見つかりました！")
    else:
        print("\n❌ 'AddArcs' メソッドは見つかりませんでした。")

except Exception as e:
    print(f"エラーが発生しました: {e}")