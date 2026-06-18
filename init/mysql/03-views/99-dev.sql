CREATE VIEW V_ship_ownership_stats AS
SELECT
    b.ship_id,
    b.tier,
    t.name AS type,
    n.name AS nation,
    b.ship_name,
    ROUND(COALESCE(s.ship_users, 0) / NULLIF(m.metric_value, 0) * 100, 2) 
        AS ownership_rate,
    ROUND(COALESCE(s.total_battles, 0) / NULLIF(s.ship_users, 0), 2) 
        AS avg_battles_per_user
FROM T_ship_base b
INNER JOIN D_ship_type t ON b.type_id = t.id
INNER JOIN D_ship_nation n ON b.nation_id = n.id
LEFT JOIN T_ship_pvp_stats s ON b.ship_id = s.ship_id
CROSS JOIN (
    SELECT metric_value 
    FROM T_table_meta 
    WHERE table_name = 'user_pvp' 
      AND metric_key = 'total_users'
    LIMIT 1
) m;