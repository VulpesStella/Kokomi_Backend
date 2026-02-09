
namespace KokomiPJ_Dashboard_BLL.Models.Entities.ShipInfo;

/// <summary>
/// 船只主表（与语言无关的属性）
/// <para>对应 MySQL 表：T_Ship_WG</para>
/// <para>一条记录 = 一艘船</para>
/// </summary>
[SugarTable("T_Ship_WG")]
public class T_Ship_WG
{
    #region 基础字段（与语言无关）

    /// <summary>
    /// 船只ID（例如：3765352144）
    /// <para>主键</para>
    /// </summary>
    [SugarColumn(IsPrimaryKey =true)]
    public long F_ShipId { get; set; }

    /// <summary>
    /// 等级（tier）
    /// <para>通常范围：1-11（具体以数据源为准）</para>
    /// </summary>
    public byte F_Tier { get; set; }

    /// <summary>
    /// 舰种（例如：Cruiser/Destroyer/Battleship/Carrier/Submarine...）
    /// <para>对应字段：F_ShipType</para>
    /// </summary>
    public string F_ShipType { get; set; } = string.Empty;

    /// <summary>
    /// 国家（例如：japan/usa/ussr...）
    /// <para>对应字段：F_Nation</para>
    /// </summary>
    public string F_Nation { get; set; } = string.Empty;

    /// <summary>
    /// 是否金币船（premium）
    /// <para>MySQL 存储为 TINYINT(1)：0/1</para>
    /// </summary>
    public bool F_Premium { get; set; }

    /// <summary>
    /// 是否特种船（special）
    /// <para>MySQL 存储为 TINYINT(1)：0/1</para>
    /// </summary>
    public bool F_Special { get; set; }

    /// <summary>
    /// 船只索引/编号（例如：PJSC505）
    /// <para>对应字段：F_ShipIndex</para>
    /// </summary>
    public string F_ShipIndex { get; set; } = string.Empty;

    #endregion

    #region 审计字段

    /// <summary>
    /// 创建人名称
    /// </summary>
    public string F_CreateUserName { get; set; } = string.Empty;

    /// <summary>
    /// 创建人ID
    /// </summary>
    public string F_CreateUserId { get; set; } = string.Empty;

    /// <summary>
    /// 创建时间
    /// </summary>
    public DateTime F_CreateTime { get; set; }

    /// <summary>
    /// 修改人名称
    /// <para>允许为空：代表尚未发生修改</para>
    /// </summary>
    public string? F_UpdateUserName { get; set; }

    /// <summary>
    /// 修改人ID
    /// <para>允许为空：代表尚未发生修改</para>
    /// </summary>
    public string? F_UpdateUserId { get; set; }

    /// <summary>
    /// 修改时间
    /// <para>允许为空：代表尚未发生修改</para>
    /// </summary>
    public DateTime? F_UpdateTime { get; set; }

    #endregion
}
