using KokomiPJ_Dashboard_BLL.BLLS.ShipInfo.IBLL;
using KokomiPJ_Dashboard_BLL.Models.Dtos.ShipInfo;
using KokomiPJ_Dashboard_BLL.Models.Entities.ShipInfo;

using LinqKit;

namespace KokomiPJ_Dashboard_BLL.BLLS.ShipInfo.BLL;

/// <summary>
/// 舰船信息管理
/// </summary>
public class ShipInfoBLL : DBServiceBase, IShipInfoBLL
{
    /// <inheritdoc/>
    public Task<PagedResult<V_Ship_WG_Names>> GetWGShipNameList
        (PageRequestDto<ShipInfoReqDto> pageRequest)
    {
        // 如果expression为空，默认给一个t => true
        Expression<Func<V_Ship_WG_Names, bool>> condition = t => true;

        // 使用 LinqKit 的 PredicateBuilder 来动态拼接条件
        var predicate = PredicateBuilder.New(condition);

        // 查询等级范围
        if (pageRequest.KeyWord?.F_Tier?.Count() != 0)
        {
            predicate = predicate.And(t => pageRequest.KeyWord.F_Tier.Contains(t.F_Tier)); 
        }

        //查询国家范围
        if (pageRequest.KeyWord?.F_Nation.Count() != 0)
        {
            predicate = predicate.And(t => pageRequest.KeyWord.F_Nation.Contains(t.F_Nation!));
        }

        //名称模糊查询(无视语言类别，允许查询任何语言类型)
        if (!string.IsNullOrEmpty(pageRequest.KeyWord?.F_Name))
        {
            predicate = predicate.And(t =>
                t.F_NameCn!.Contains(pageRequest.KeyWord.F_Name) ||
                t.F_NameEn!.Contains(pageRequest.KeyWord.F_Name) ||
                t.F_NameEnL!.Contains(pageRequest.KeyWord.F_Name) ||
                t.F_NameJa!.Contains(pageRequest.KeyWord.F_Name) ||
                t.F_NameRu!.Contains(pageRequest.KeyWord.F_Name));
        }

        //舰船类型模糊查询
        if ( pageRequest.KeyWord?.F_ShipType?.Count() != 0)
        {
            predicate = predicate.And(t => 
            pageRequest.KeyWord.F_ShipType.Contains(t.F_ShipType!));
        }

        //勾选是否是特种船
        if (pageRequest.KeyWord?.F_Special == true)
        {
            predicate = predicate.And(t => t.F_Special == true);
        }

        //勾选是否是金币船
        if (pageRequest.KeyWord?.F_Premium == true)
        {
            predicate = predicate.And(t => t.F_Premium == true);
        }

        return Repository("ships")
            .GetPagedDataAsync<V_Ship_WG_Names>(pageRequest, predicate);
    }
}
