import crypto from 'node:crypto';
import { gunzipSync } from 'node:zlib';
import * as signalr from '@microsoft/signalr';
import { MessagePackHubProtocol } from '@microsoft/signalr-protocol-msgpack';

const api = process.env.LNS_API || 'https://api.lightnovel.life';
const sha256 = (s) => crypto.createHash('sha256').update(s).digest('hex');

const login = await (
  await fetch(`${api}/api/user/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({ email: process.env.LNS_EMAIL, password: sha256(process.env.LNS_PASSWORD) }),
  })
).json();

if (!login.Success) throw new Error(`login: ${login.Msg ?? login.Status}`);

const conn = new signalr.HubConnectionBuilder()
  .withUrl(`${api}/hub/api`, { accessTokenFactory: () => login.Response.Token })
  .withHubProtocol(new MessagePackHubProtocol())
  .build();

await conn.start();
const { Success, Response, Msg, Status } = await conn.invoke('SignIn', {}, { UseGzip: true });
await conn.stop();

if (!Success) {
  if (`${Msg}`.includes('已签到')) {
    console.log('今日已签到，跳过');
    process.exit(0);
  }
  throw new Error(`signin: ${Msg ?? Status}`);
}
const data = Response instanceof Uint8Array ? JSON.parse(gunzipSync(Buffer.from(Response)).toString()) : Response;

// 与轻书架 Web 端字段口径一致：
// Reward=本次经验 CoinReward=本次金币 Streak=连签天数 Exp=累计经验 Coin=金币余额 Level=当前等级
const { Reward = 0, CoinReward = 0, Streak = 0, Exp = 0, Coin = 0, Level = 0 } = data ?? {};
const dateStr = new Date().toLocaleString('zh-CN', {
  timeZone: 'Asia/Shanghai',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
});

console.log(`轻书架签到成功（${dateStr} 北京时间）`);
console.log(`- 连续签到：${Streak} 天`);
console.log(`- 本次奖励：经验 +${Reward}，金币 +${CoinReward}`);
console.log(`- 当前等级：Lv.${Level}（累计经验 ${Exp}）`);
console.log(`- 金币余额：${Coin}`);
console.log(`原始数据：${JSON.stringify(data)}`);
