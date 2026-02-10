using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace KokomiPJ_Dashboard_BLL.Models.Entities.ShipInfo;

/// <summary>
/// 对应数据库视图：V_Ship_WG_Names
/// <para>来源：T_Ship_WG + T_ShipNameI18n</para>
/// <para>作用：把多语言船名（cn/en/en_l/ja/ru）聚合为一行多列（F_NameCn/F_NameEn/...）</para>
/// </summary>
[SugarTable("V_Ship_WG_Names")]
public class V_Ship_WG_Names
{
    #region 主表字段（来自 T_Ship_WG）

    /// <summary>
    /// 船只ID（例如：3765352144）
    /// <para>视图本身通常没有物理主键，但该字段在业务上可视作唯一标识（一船一行）</para>
    /// </summary>
    [SugarColumn(ColumnName = "F_ShipId", IsPrimaryKey = true)]
    public long F_ShipId { get; set; }

    /// <summary>
    /// 等级（tier）
    /// </summary>
    [SugarColumn(ColumnName = "F_Tier")]
    public byte F_Tier { get; set; }

    /// <summary>
    /// 舰种（Cruiser/Destroyer/...）
    /// </summary>
    [SugarColumn(ColumnName = "F_ShipType")]
    public string? F_ShipType { get; set; }

    /// <summary>
    /// 国家（japan/usa/...）
    /// </summary>
    [SugarColumn(ColumnName = "F_Nation")]
    public string? F_Nation { get; set; }

    /// <summary>
    /// 是否金币船（premium）
    /// </summary>
    [SugarColumn(ColumnName = "F_Premium")]
    public bool? F_Premium { get; set; }

    /// <summary>
    /// 是否特种船（special）
    /// </summary>
    [SugarColumn(ColumnName = "F_Special")]
    public bool? F_Special { get; set; }

    /// <summary>
    /// 索引/编号（例如：PJSC505）
    /// </summary>
    [SugarColumn(ColumnName = "F_ShipIndex")]
    public string? F_ShipIndex { get; set; }

    #endregion

    #region 多语言名称列（来自 T_ShipNameI18n，经 MAX(CASE...) 聚合）

    /// <summary>
    /// 船名（中文 cn）
    /// <para>由：MAX(CASE WHEN n.F_LangCode = 'cn' THEN n.F_ShipName END)</para>
    /// </summary>
    [SugarColumn(ColumnName = "F_NameCn")]
    public string? F_NameCn { get; set; }

    /// <summary>
    /// 船名（英文 en）
    /// </summary>
    [SugarColumn(ColumnName = "F_NameEn")]
    public string? F_NameEn { get; set; }

    /// <summary>
    /// 船名（英文长名 en_l）
    /// </summary>
    [SugarColumn(ColumnName = "F_NameEnL")]
    public string? F_NameEnL { get; set; }

    /// <summary>
    /// 船名（日文 ja）
    /// </summary>
    [SugarColumn(ColumnName = "F_NameJa")]
    public string? F_NameJa { get; set; }

    /// <summary>
    /// 船名（俄文 ru）
    /// </summary>
    [SugarColumn(ColumnName = "F_NameRu")]
    public string? F_NameRu { get; set; }

    #endregion
}
