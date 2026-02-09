
using KokomiPJ_Dashboard_BLL.BLLS.ShipInfo.IBLL;
using KokomiPJ_Dashboard_BLL.Models.Entities.ShipInfo;



namespace KokomiPJ_Dashboard_BLL.BLLS.ShipInfo.BLL;

/// <summary>
/// 船信息管理
/// </summary>
public class ShipInfoBLL : DBServiceBase, IShipInfoBLL
{
    /// <inheritdoc/>
    public Task<PagedResult<V_Ship_WG_Names>> GetWGShipNameList
        (PageRequestDto<V_Ship_WG_Names> pageRequest, 
         Expression<Func<V_Ship_WG_Names, bool>>? expression = null)
    {
       return Repository("ships")
            .GetPagedDataAsync(pageRequest, expression);
    }
}
