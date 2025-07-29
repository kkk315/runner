
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

### 3.ネットワーク作成
swarm外からコード実行用コンテナが参加できるよう、アタッチ可能なネットワークを事前に作成します。
```
docker network create --driver overlay --attachable runner_backend-db-net
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

### 開発環境起動（ホスト）
#### フロントエンド
```bash
cd frontend/
npm start
```
#### バックエンド
```bash
cd backend
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

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
