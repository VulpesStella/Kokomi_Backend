namespace KokomiPJ_Dashboard.Controllers.MVC;

public class AppController:Controller
{
    /// <summary>
    /// 指向VBen
    /// </summary>
    /// <returns></returns>
    [Route("app")]
    [Route("app/{*path}")]
    public IActionResult Index()
    {
        return View();
    }
}
