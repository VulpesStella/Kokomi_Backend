
using KokomiPJ_Dashboard_BLL.Models.Entities.ShipInfo;

namespace KokomiPJ_Dashboard_BLL.BLLS.ShipInfo.IBLL;

/// <summary>
/// 舰船管理功能接口
/// </summary>
public interface IShipInfoBLL
{
    /// <summary>
    /// 分页查询船名信息（WG版本）
    /// </summary>
    /// <param name="pageRequest">分页数据</param>
    /// <param name="expression">查询条件</param>
    /// <returns></returns>
    Task<PagedResult<V_Ship_WG_Names>> GetWGShipNameList
        (PageRequestDto<V_Ship_WG_Names> pageRequest,
         Expression<Func<V_Ship_WG_Names, bool>>? expression = null);
}
