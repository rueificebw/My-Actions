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
console.log(JSON.stringify(data));
