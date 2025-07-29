
---
# runner
オンライン実行環境です。

# ビルドコマンド
```bash

docker build -t runner-backend:latest ./backend
docker build -t runner-frontend:latest ./frontend

```

## 本番運用・初回セットアップ手順
### 1. Docker Swarm 初期化（初回）
```
docker swarm init
```
### 2. シークレット登録（初回）

`register-secrets.sh` に実行権限を付与し、スクリプトで一括登録します。

```
chmod +x register-secrets.sh
./register-secrets.sh
```


### Swarm（本番環境）停止・開始

#### Swarm停止
```bash
docker stack rm runner
```
#### Swarm開始
```bash
docker stack deploy -c docker-compose.yml runner
```

### 開発環境起動
#### compose開始
```bash
docker compose -f docker-compose.dev.yml up -d
```
#### compose停止
```bash
docker compose -f docker-compose.dev.yml down
```

※本番は `docker-compose.yml`、開発は `docker-compose.dev.yml` を使用
※開発composeはsecrets不要、DBはdev用設定
※ネットワークはbridge、ポートはローカル向け

### runnerビルド
```bash
docker build -t runner-python:latest -f runner/Dockerfile.python ./runner
docker build -t runner-node:latest -f runner/Dockerfile.node ./runner
```

---

### 備考
- Swarmシークレットは `secrets.env.example` を参考に環境変数を登録。
- `register-secrets.sh` は `secrets.env.example` の内容を一括登録するスクリプト。
- runnerはAPI経由で動的に起動されるため、composeで常時起動する必要はありません。
- ネットワーク分離（frontend-net, backend-db-net）は `docker-compose.yml` で定義済み。
