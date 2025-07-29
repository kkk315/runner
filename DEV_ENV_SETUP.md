# 開発環境手順書

## Swarm停止手順
1. 現在のSwarmスタックを停止・削除
   ```bash
   docker stack rm runner
   ```
2. Swarmネットワークや不要なサービスが残っている場合は手動で削除
   ```bash
   docker network ls
   docker network rm <不要なネットワーク名>
   docker service ls
   docker service rm <不要なサービス名>
   ```

## 開発環境起動手順
1. 開発用composeファイルで起動
   ```bash
   docker compose -f docker-compose.dev.yml up --build
   ```
2. backend, frontend, dbがローカルボリュームでホットリロード対応
   - backend: `./backend:/app` マウント、`uvicorn --reload`
   - frontend: `./frontend:/app` マウント、`npm start`（Reactホットリロード）
   - db: 開発用ユーザー/パスワード/DB名

3. 停止は通常通り
   ```bash
   docker compose -f docker-compose.dev.yml down
   ```

## 注意事項
- 本番用compose（Swarm）は `docker-compose.yml`、開発用は `docker-compose.dev.yml` を使用
- secretsや本番用DB設定は開発composeでは不要
- 開発用ネットワークはbridge、ポートはローカル向け
