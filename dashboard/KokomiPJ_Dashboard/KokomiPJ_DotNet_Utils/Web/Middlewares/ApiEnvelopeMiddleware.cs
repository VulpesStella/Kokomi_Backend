

using KokomiPJ_DotNet_Utils.Models.Dto;

using Microsoft.AspNetCore.Http;


using System.Text;
namespace KokomiPJ_DotNet_Utils.Web.Middlewares
{
    /// <summary>
    /// API 统一返回壳中间件(对齐猫鱼的API模型)
    /// <para>将 /api 下的 JSON 响应统一包装成 ApiEnvelopeRaw{T}</para>
    /// </summary>
    public sealed class ApiEnvelopeMiddleware
    {
        private readonly RequestDelegate _next;

        /// <summary>
        /// 构造函数
        /// </summary>
        /// <param name="next">下一个中间件</param>
        public ApiEnvelopeMiddleware(RequestDelegate next)
        {
            _next = next;
        }

        /// <summary>
        /// 中间件主逻辑
        /// </summary>
        /// <param name="context">HTTP上下文</param>
        public async Task InvokeAsync(HttpContext context)
        {
            // 仅处理 API 路径
            if (!context.Request.Path.StartsWithSegments("/api", StringComparison.OrdinalIgnoreCase))
            {
                await _next(context);
                return;
            }

            // 先把原响应流替换成内存流，便于读取与二次输出
            var originalBodyStream = context.Response.Body;
            await using var bufferStream = new MemoryStream();
            context.Response.Body = bufferStream;

            try
            {
                await _next(context);

                // 如果已经开始写响应头了，就别动了（避免破坏响应）
                if (context.Response.HasStarted)
                {
                    bufferStream.Position = 0;
                    await bufferStream.CopyToAsync(originalBodyStream);
                    return;
                }

                // 只处理 JSON
                var contentType = context.Response.ContentType ?? string.Empty;
                if (!contentType.Contains("application/json", StringComparison.OrdinalIgnoreCase))
                {
                    bufferStream.Position = 0;
                    await bufferStream.CopyToAsync(originalBodyStream);
                    return;
                }

                // 读取原始 body 文本
                bufferStream.Position = 0;
                var rawBody = await new StreamReader(bufferStream, Encoding.UTF8).ReadToEndAsync();

                // 为空也要包壳（Data = null）
                JToken? dataToken = null;
                if (!string.IsNullOrWhiteSpace(rawBody))
                {
                    // 如果本来就是 envelope，就不二次包装（避免套娃）
                    if (LooksLikeEnvelope(rawBody))
                    {
                        // 原样输出
                        await WriteRawAsync(context, originalBodyStream, rawBody);
                        return;
                    }

                    // 尝试当 JSON 解析；解析失败则按字符串当 data
                    dataToken = TryParseJson(rawBody) ?? JValue.CreateString(rawBody);
                }

                // 构建 envelope（保持 HTTP 状态码不变）
                var statusCode = context.Response.StatusCode;
                var envelope = new ApiEnvelopeRaw<JToken?>
                {
                    Status = IsSuccessStatus(statusCode) ? "success" : "error",
                    Code = statusCode,
                    Message = IsSuccessStatus(statusCode) ? "success" : "error",
                    Data = dataToken
                };

                var wrappedJson = JsonConvert.SerializeObject(envelope, Newtonsoft.Json.Formatting.None);

                // 输出包装后的响应
                context.Response.ContentType = "application/json; charset=utf-8";
                context.Response.ContentLength = Encoding.UTF8.GetByteCount(wrappedJson);

                await WriteRawAsync(context, originalBodyStream, wrappedJson);
            }
            finally
            {
                // 还原响应流
                context.Response.Body = originalBodyStream;
            }
        }

        /// <summary>
        /// 判断 HTTP 状态码是否属于成功范围（2xx）
        /// </summary>
        private static bool IsSuccessStatus(int statusCode) => statusCode >= 200 && statusCode <= 299;

        /// <summary>
        /// 粗略判断 body 是否已经是 envelope（避免二次包装）
        /// </summary>
        private static bool LooksLikeEnvelope(string rawBody)
        {
            try
            {
                var token = JToken.Parse(rawBody);
                if (token.Type != JTokenType.Object) return false;

                var obj = (JObject)token;
                // 必要字段存在即可认为是 envelope
                return obj.ContainsKey("status") && obj.ContainsKey("code") && obj.ContainsKey("message") && obj.ContainsKey("data");
            }
            catch
            {
                return false;
            }
        }

        /// <summary>
        /// 尝试解析 JSON 文本为 JToken，失败返回 null
        /// </summary>
        private static JToken? TryParseJson(string rawBody)
        {
            try
            {
                return JToken.Parse(rawBody);
            }
            catch
            {
                return null;
            }
        }

        /// <summary>
        /// 将文本写回原始响应流
        /// </summary>
        private static async Task WriteRawAsync(HttpContext context, Stream originalBodyStream, string text)
        {
            // 重要：写回之前清空缓冲，避免把旧内容一起输出
            await using var outStream = new MemoryStream(Encoding.UTF8.GetBytes(text));
            outStream.Position = 0;
            await outStream.CopyToAsync(originalBodyStream);
        }
    }
}
