def calc_ship_rating_python(ship_data: list, server_data: list):
    """Python版本实现 - 仅计算PR值"""
    print("\n=== Python计算过程 ===")
    print(f"ship_data: {ship_data}")
    print(f"server_data: {server_data}")
    
    # 获取服务器数据检查
    if server_data[0] is None or server_data[0] < 1000:
        print(f"server_data[0]={server_data[0]} < 1000，返回 -1")
        return -1
    print(f"server_data[0]={server_data[0]} >= 1000，继续计算")
    
    # Step 1 - ratios
    r_wins = ship_data[0] / server_data[1]
    r_dmg = ship_data[1] / server_data[2]
    r_frags = ship_data[2] / server_data[3]
    print(f"\nStep 1 - 比率:")
    print(f"  r_wins = {ship_data[0]} / {server_data[1]} = {r_wins}")
    print(f"  r_dmg = {ship_data[1]} / {server_data[2]} = {r_dmg}")
    print(f"  r_frags = {ship_data[2]} / {server_data[3]} = {r_frags}")
    
    # Step 2 - normalization
    n_wins = max(0, (r_wins - 0.7) / (1 - 0.7))
    n_dmg = max(0, (r_dmg - 0.4) / (1 - 0.4))
    n_frags = max(0, (r_frags - 0.1) / (1 - 0.1))
    print(f"\nStep 2 - 归一化:")
    print(f"  n_wins = max(0, ({r_wins} - 0.7) / 0.3) = {n_wins}")
    print(f"  n_dmg = max(0, ({r_dmg} - 0.4) / 0.6) = {n_dmg}")
    print(f"  n_frags = max(0, ({r_frags} - 0.1) / 0.9) = {n_frags}")
    
    # Step 3 - PR value
    personal_rating = round(700 * n_dmg + 300 * n_frags + 150 * n_wins, 2)
    print(f"\nStep 3 - PR计算:")
    print(f"  700 * {n_dmg} = {700 * n_dmg}")
    print(f"  300 * {n_frags} = {300 * n_frags}")
    print(f"  150 * {n_wins} = {150 * n_wins}")
    print(f"  总和 = {700 * n_dmg + 300 * n_frags + 150 * n_wins}")
    print(f"  round后 = {personal_rating}")
    
    return personal_rating


# 使用示例
if __name__ == "__main__":
    # 替换为你的数据
    ship_data = [69.277, 94042, 1.35]  # [wins, damage, frags]
    server_data = [810212, 55.74, 70361.2, 0.92]  # [battles, expected_wins, expected_dmg, expected_frags]
    
    result = calc_ship_rating_python(ship_data, server_data)
    print(f"\n最终结果: {result}")