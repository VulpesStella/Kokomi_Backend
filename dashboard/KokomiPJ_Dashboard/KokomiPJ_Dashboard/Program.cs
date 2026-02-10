using KokomiPJ_DotNet_Utils.Web.Extensions;
using KokomiPJ_DotNet_Utils.Web.Middlewares;

using Vanguard_DB.DI;

namespace KokomiPJ_Dashboard;

/// <summary>
/// 程序启动入口
/// </summary>
public class Program
{
    public static void Main(string[] args)
    {
        var builder = WebApplication.CreateBuilder(args);

        #region 配置MVC页面

        // Add services to the container.
        var mvc = builder.Services.AddControllersWithViews();

        //增加启用Razor页面热更新
        if (builder.Environment.IsDevelopment())
        {
            mvc.AddRazorRuntimeCompilation();
        }

        #endregion

        #region 配置Http请求（主要是跟耄鱼的API交互）

        //往DI容器内注入HttpclientFactory
        builder.Services.AddHttpClient();

        //读取Appsetting.json中的API选项相关作为
        builder.Services.Configure<KokomiAPIOptions>(
        builder.Configuration.GetSection("KokomiAPIOptions"));

        //为API请求业务注入HttpClient
        builder.Services.AddHttpClient<IAPIStatusBLL, APIStatusBLL>((sp, client) =>
        {
            var opt = sp.GetRequiredService
            <Microsoft.Extensions.Options.IOptions<KokomiAPIOptions>>().Value;

            if (!string.IsNullOrWhiteSpace(opt.BaseUrl))
                client.BaseAddress = new Uri(opt.BaseUrl);

            client.Timeout = TimeSpan.FromSeconds(10);
        });

        #endregion

        //获取应用所有DLL
        var assemblies = new[]
        {
            typeof(Program).Assembly,
            typeof(KokomiPJ_Dashboard_BLL.Anchor).Assembly  
        };

        //启动VanguardDbHelper的DI注入
        builder.AddVanguardDbHelper(assemblies);
        // 注册 Swagger
        builder.Services.AddKokomiSwagger(title: "KokomiAPI_DotNet", 
            version: "v1",summery:"KokomiAPI的.NET 版API", 
            descriptions:"基于.NET8", 
            enableXmlComments: true,xmlAssemblies: assemblies);

        var app = builder.Build();

        app.UseMiddleware<ApiEnvelopeMiddleware>(); 
        // 启用 Swagger UI
        app.UseKokomiDotNetSwagger(version: "v1", routePrefix: "swagger", onlyInDevelopment: true);

        // Configure the HTTP request pipeline.
        if (!app.Environment.IsDevelopment())
        {
            app.UseExceptionHandler("/Home/Error");
        }
        app.UseStaticFiles();

        app.UseRouting();

        app.UseAuthorization();
        //默认启动时指向Home/Index
        app.MapControllerRoute(
            name: "default",
            pattern: "{controller=Home}/{action=Index}/{id?}");

        app.Run();
    }
}