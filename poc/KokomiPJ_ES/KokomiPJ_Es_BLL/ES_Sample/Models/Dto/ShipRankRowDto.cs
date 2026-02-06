
namespace KokomiPJ_Es_BLL.ES_Sample.Models;

/// <summary>
/// kokomi_单船排行榜数据模型Dto
/// </summary>
public class ShipRankRowDto
{
    /// <summary>
    /// 自增主键
    /// </summary>
    public int Id { get; set; }

    /// <summary>
    /// 账号主键
    /// </summary>
    public long Account_Id { get; set; }

    /// <summary>
    /// 用户昵称
    /// </summary>
    public string? Username { get; set; }

    /// <summary>
    /// 区服
    /// </summary>
    public sbyte Region_Id { get; set; }

    /// <summary>
    /// 总场次
    /// </summary>
    public int Battles_Count { get; set; }

    /// <summary>
    /// 单人组队
    /// </summary>
    public int Battle_Type_1 { get; set; }

    /// <summary>
    /// 双人组队
    /// </summary>
    public int Battle_Type_2 { get; set; }

    /// <summary>
    /// 三人组队
    /// </summary>
    public int Battle_Type_3 { get; set; }

    /// <summary>
    /// 总胜场
    /// </summary>
    public int Wins { get; set; }

    /// <summary>
    /// 总伤害
    /// </summary>
    public long Damage_Dealt { get; set; }

    /// <summary>
    /// 总击杀
    /// </summary>
    public int Frags { get; set; }

    /// <summary>
    /// 总经验
    /// </summary>
    public long Exp { get; set; }

    /// <summary>
    /// 总幸存数
    /// </summary>
    public int Survived { get; set; }

    /// <summary>
    /// 总侦查伤害
    /// </summary>
    public long Scouting_Damage { get; set; }

    /// <summary>
    /// 这啥啊
    /// </summary>
    public long Art_Agro { get; set; }

    /// <summary>
    /// 总击落飞机
    /// </summary>
    public int Planes_Killed { get; set; }

    /// <summary>
    /// 最大经验记录
    /// </summary>
    public int Max_Exp { get; set; }

    /// <summary>
    /// 最大伤害记录
    /// </summary>
    public int Max_Damage_Dealt { get; set; }

    /// <summary>
    /// 最大击杀记录
    /// </summary>
    public int Max_Frags { get; set; }

    /// <summary>
    /// 创建记录日
    /// </summary>
    public DateTime Created_At { get; set; }

    /// <summary>
    /// 数据最近更新
    /// </summary>
    public DateTime Updated_At { get; set; }
}
