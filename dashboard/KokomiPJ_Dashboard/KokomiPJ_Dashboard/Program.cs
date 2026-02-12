using KokomiPJ_DotNet_Utils.Web.Extensions;
using KokomiPJ_DotNet_Utils.Web.Middlewares;

using Vanguard_DB.DI;

using Vite.AspNetCore;

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

        #region 启用Vite
        // 注册 Vite 服务
        builder.Services.AddViteServices(options =>
        {
            options.Base = "app";              // 你的静态资源在 wwwroot/app 下
            options.Manifest = "manifest.json"; // 你现在的 manifest 在 /app/manifest.json
        });
        builder.Services.AddReverseProxy()
        .LoadFromConfig(builder.Configuration.GetSection("ReverseProxy"));
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
        app.MapReverseProxy();
        app.UseMiddleware<ApiEnvelopeMiddleware>(); 
        // 启用 Swagger UI
        app.UseKokomiDotNetSwagger(version: "v1", routePrefix: "swagger", onlyInDevelopment: true);

        // Configure the HTTP request pipeline.
        if (!app.Environment.IsDevelopment())
        {
            app.UseExceptionHandler("/Home/Error");
        }
        else
        {
            //启用WebSocket(开发阶段)
            //允许Vite 实时更新
            app.UseWebSockets();
            //允许从 MVC 的域名/端口访问前端资源”
            app.UseViteDevelopmentServer();
        }
        app.UseStaticFiles();

        app.UseRouting();

        app.UseAuthorization();
        //默认启动时指向Home/Index
        app.MapControllerRoute(
            name: "default",
            pattern: "{controller=Home}/{action=Index}/{id?}");
        app.MapControllerRoute(
        name: "vben-app",
        pattern: "app/{**path}",
        defaults: new { controller = "app", action = "Index" });


        app.MapFallbackToFile("/app/{*path:nonfile}", "app/index.html");
        app.Run();
    }
}