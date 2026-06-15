class RatingUtils:
    def calculate_rating(
        game_type: str,
        ship_data: dict,
        server_data: list
    ):
        if server_data is None or server_data == []:
            return
        
        if ship_data is None or ship_data == {}:
            return
        
        battles_count = ship_data['battles_count']
        if battles_count <= 0:
            ship_data['personal_rating'] = -1
            ship_data['damage_rating'] = -1
            ship_data['frags_rating'] = -1
            return
        
        # 用户数据
        actual_wins = ship_data['wins'] / battles_count * 100
        actual_dmg = ship_data['damage_dealt'] / battles_count
        actual_frags = ship_data['frags'] / battles_count

        # 服务器数据
        expected_wins = server_data[0]
        expected_dmg = server_data[1]
        expected_frags = server_data[2]

        # 计算PR
        # Step 1 - ratios:
        r_wins = actual_wins / expected_wins
        r_dmg = actual_dmg / expected_dmg
        r_frags = actual_frags / expected_frags

        # Step 2 - normalization:
        n_wins = max(0, (r_wins - 0.7) / (1 - 0.7))
        n_dmg = max(0, (r_dmg - 0.4) / (1 - 0.4))
        n_frags = max(0, (r_frags - 0.1) / (1 - 0.1))

        # Step 3 - PR value:
        if game_type in ['rank', 'rank_solo', 'rating_solo', 'rating_div']:
            personal_rating = 600 * n_dmg + 350 * n_frags + 400 * n_wins
        else:
            personal_rating = 700 * n_dmg + 300 * n_frags + 150 * n_wins

        ship_data['personal_rating'] = round(personal_rating, 2)
        ship_data['damage_rating'] = round(actual_dmg / expected_dmg, 2)
        ship_data['frags_rating'] = round(actual_frags / expected_frags, 2)
        return
    
    def get_rating_level(
        rating: int | float, 
        show_eggshell: bool = False
    ):
        if rating == -1:
            return 0
        
        if show_eggshell:
            data = [750, 1100, 1350, 1550, 1750, 2100, 2450, 3250]
            for i in range(len(data)):
                if rating < data[i]:
                    return i + 1, int(data[i]-rating)
            return 9
        else:
            data = [750, 1100, 1350, 1550, 1750, 2100, 2450]
            for i in range(len(data)):
                if rating < data[i]:
                    return i + 1, int(data[i]-rating)
            return 8
    
    def get_wr_rating_class(rating: int | float):
        if rating == -1:
            return 0
        data = [40, 45, 50, 52.5, 55, 60, 67]
        for i in range(len(data)):
            if rating < data[i]:
                return i + 1
        return 8
    
    def get_metric_level(metric_id: int, value: float) -> int:
        thresholds_map = {
            0: [40, 45, 50, 52.5, 55, 60, 67],           # win_rate 等级阈值
            1: [0.8, 0.95, 1.0, 1.1, 1.2, 1.4, 1.7],     # avg_damage 等级阈值
            2: [0.2, 0.3, 0.6, 1.0, 1.3, 1.5, 2.0],      # avg_frags 等级阈值
            3: [750, 1100, 1350, 1550, 1750, 2100, 2450] # rating 等级阈值
        }

        thresholds = thresholds_map.get(metric_id)
        if thresholds is None:
            return 0

        # 计算满足 value >= threshold 的数量
        count = sum(1 for th in thresholds if value >= th)
        return 1 + count