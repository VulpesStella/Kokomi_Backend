

namespace KokomiPJ_Dashboard_BLL.Models.Entities.ShipInfo;

/// <summary>
/// 船名多语言表（每种语言一行）
/// <para>对应 MySQL 表：T_ShipNameI18n</para>
/// <para>复合主键：(F_ShipId, F_LangCode)</para>
/// </summary>
[SugarTable("T_ShipNameI18n")]
public class T_ShipNameI18n
{
    #region 主键/业务字段

    /// <summary>
    /// 船只ID
    /// <para>外键关联：T_Ship_WG.F_ShipId</para>
    /// </summary>
    
    public long F_ShipId { get; set; }

    /// <summary>
    /// 语言代码（cn/en/en_l/ja/ru）
    /// <para>复合主键的一部分</para>
    /// </summary>
    public string F_LangCode { get; set; } = string.Empty;

    /// <summary>
    /// 对应语言下的船名（例如：矢矧 / Yahagi）
    /// </summary>
    public string F_ShipName { get; set; } = string.Empty;

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

/// <summary>
/// 船名语言代码常量
/// <para>用于避免手写字符串拼错</para>
/// </summary>
public static class ShipLangCodes
{
    /// <summary>中文</summary>
    public const string Cn = "cn";

    /// <summary>英文（短名）</summary>
    public const string En = "en";

    /// <summary>英文（长名 / 本地化字段 en_l）</summary>
    public const string EnL = "en_l";

    /// <summary>日文</summary>
    public const string Ja = "ja";

    /// <summary>俄文</summary>
    public const string Ru = "ru";
}