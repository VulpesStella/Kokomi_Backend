
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.OpenApi;
using System.Reflection;

namespace KokomiPJ_DotNet_Utils.Web.Extensions;

/// <summary>
/// Swagger 扩展方法
/// </summary>
public static class SwaggerExtensions
{
    /// <summary>
    /// 注册 Swagger
    /// </summary>
    public static IServiceCollection AddKokomiSwagger(
        this IServiceCollection services,
        string title = "KokomiAPI_DotNet",
        string version = "v1",
        string summery="",
        string descriptions = "",
        bool enableXmlComments = true,
        params Assembly[] xmlAssemblies)
    {
        services.AddEndpointsApiExplorer();

        services.AddSwaggerGen(c =>
        {
            c.SwaggerDoc(version, new OpenApiInfo { Title = title, Version = version,Summary = summery,
                Description = summery,
            });

            // 只收集标了 [ApiController] 的控制器(以免把MVC路由也给误卷入)
            c.DocInclusionPredicate((docName, apiDesc) =>
                apiDesc.ActionDescriptor.EndpointMetadata.OfType<ApiControllerAttribute>().Any());

            // 默认：Bearer Token（Swagger UI 右上角 Authorize）
            var scheme = new OpenApiSecurityScheme
            {
                Name = "Authorization",
                Description = "输入：Bearer {token}（Bearer 后有空格）",
                In = ParameterLocation.Header,
                Type = SecuritySchemeType.Http,
                Scheme = "bearer",
                BearerFormat = "JWT",
            };

            c.AddSecurityDefinition("Bearer", scheme);
            c.AddSecurityRequirement(doc => new OpenApiSecurityRequirement
            {
                { new OpenApiSecuritySchemeReference("Bearer"), new List<string>() }
            });

            //  是否启用XML 注释（可选是否启用）
            if (enableXmlComments)
            {
                // 没传就默认用入口程序集
                var asms = (xmlAssemblies != null && xmlAssemblies.Length > 0)
                    ? xmlAssemblies
                    : new[] { Assembly.GetEntryAssembly() ?? Assembly.GetExecutingAssembly() };

                foreach (var asm in asms.Distinct())
                {
                    var xmlFile = $"{asm.GetName().Name}.xml";
                    var xmlPath = Path.Combine(AppContext.BaseDirectory, xmlFile);

                    if (File.Exists(xmlPath))
                        c.IncludeXmlComments(xmlPath, includeControllerXmlComments: true);
                }
            }
        });

        return services;
    }

    /// <summary>
    /// 启用 Swagger UI（默认只在 Development）
    /// </summary>
    public static IApplicationBuilder UseKokomiDotNetSwagger(
        this IApplicationBuilder app,
        string version = "v1",
        string routePrefix = "swagger",
        bool onlyInDevelopment = true)
    {
        var env = app.ApplicationServices.GetRequiredService<IHostEnvironment>();
        if (onlyInDevelopment && !env.IsDevelopment())
            return app;

        app.UseSwagger();
        app.UseSwaggerUI(c =>
        {
            c.SwaggerEndpoint($"/swagger/{version}/swagger.json", $"KokomiAPI_DotNet  {version}");
            c.RoutePrefix = routePrefix;
            c.DisplayRequestDuration();
        });

        return app;
    }
}

