
namespace KokomiPJ_Dashboard_BLL.Models.Dtos.ShipInfo;

/// <summary>
/// 船只信息查询条件用Dto 
/// </summary>
public class ShipInfoReqDto
{

    /// <summary>
    /// 船只ID（例如：3765352144）
    /// </summary>
    public long? F_ShipId { get; set; }

    /// <summary>
    /// 等级列表（1-11）
    /// </summary>
    public List<byte> F_Tier { get; set; } = [];

    /// <summary>
    /// 舰种（Cruiser/Destroyer/...）
    /// </summary>
    public List<string>? F_ShipType { get; set; }

    /// <summary>
    /// 国家（japan/usa/...）
    /// </summary>
    public List<string>? F_Nation { get; set; }

    /// <summary>
    /// 是否金币船（premium）
    /// </summary>
    public bool? F_Premium { get; set; }

    /// <summary>
    /// 是否特种船（special）
    /// </summary>
    public bool? F_Special { get; set; }

    /// <summary>
    /// 索引/编号（例如：PJSC505）
    /// </summary>
    public string? F_ShipIndex { get; set; }

    /// <summary>
    /// 船名（不分语言类型，默认匹配所有语言）
    /// </summary>
    public string? F_Name { get; set; }

}
