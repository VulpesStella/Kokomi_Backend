
using KokomiPJ_Dashboard_BLL.BLLS.ShipInfo.IBLL;
using KokomiPJ_Dashboard_BLL.Models.Dtos.ShipInfo;
using KokomiPJ_Dashboard_BLL.Models.Entities.ShipInfo;

using System.Linq.Expressions;

namespace KokomiPJ_Dashboard.Controllers;

/// <summary>
/// 舰船基础信息管理接口
/// </summary>
[ApiController]
[Route("api/[controller]")]
public class ShipInfoController : Controller
{
    #region 私有字段

    private readonly ILogger<HomeController> _logger;

    //API运行状况页面业务逻辑BLL
    private readonly IShipInfoBLL _iShipInfoBL;

    #endregion



    #region 构造函数

    public ShipInfoController(ILogger<HomeController> logger,
        IShipInfoBLL iShipInfoBL)
    {
        _logger = logger;
        _iShipInfoBL = iShipInfoBL;
    }

    #endregion


    #region 页面

    /// <summary>
    /// 查询WG服务的船只基础信息
    /// </summary>
    /// <returns></returns>
    [HttpPost("WGShipInfoList")]
    public async Task<IActionResult> WGShipInfoList([FromBody] PageRequestDto<ShipInfoReqDto> req)
    {
        var shipInfoList = await 
            _iShipInfoBL.GetWGShipNameList(req);
        return Ok(shipInfoList);
    }

    #endregion



}
