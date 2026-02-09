
using KokomiPJ_Dashboard_BLL.BLLS.ShipInfo.IBLL;
using KokomiPJ_Dashboard_BLL.Models.Entities.ShipInfo;

namespace KokomiPJ_Dashboard.Controllers;

/// <summary>
/// API运行情况控制器
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
    /// API运行情况页面
    /// </summary>
    /// <returns></returns>
    [HttpPost("/WGShipInfoList")]
    public async Task<IActionResult> WGShipInfoList([FromBody] PageRequestDto<V_Ship_WG_Names> req)
    {
        var shipInfoList = await 
            _iShipInfoBL.GetWGShipNameList(req);
        return Ok(shipInfoList);
    }

    #endregion



}
