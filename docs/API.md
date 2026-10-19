# API do ranking

Base: `https://ryuk.gab.dev.br/api`. JSON, sem login: cada aparelho recebe um **token** ao reservar
o apelido e o usa para enviar pontuações. O servidor guarda só o SHA-256 do token.

## `POST /api/claim`

Reserva um apelido único.

```json
{ "name": "Isa Morcega" }
```

| Resposta | Quando |
|---|---|
| `201 {"name", "token"}` | apelido reservado — guarde o token |
| `409 {"erro":"nome_em_uso"}` | já tem dono |
| `400 {"erro":"nome_invalido"}` | fora de 3–14 caracteres (letras, números, espaço, `_ . -`) |
| `400 {"erro":"nome_feio"}` | palavrão ou ofensa (o ranking é de crianças) |
| `429 {"erro":"muitas_tentativas"}` | mais de 8 cadastros por hora no mesmo IP |

**Unicidade:** a comparação ignora acento, maiúscula e pontuação — `Isa`, ` ÍSA ` e `I.s.a` são o
mesmo apelido.

## `POST /api/score`

```json
{ "token": "…", "meters": 812, "souls": 37, "secs": 61.4 }
```

`souls` é o nome interno das **bolsas de sangue** coletadas. A pontuação é recalculada no servidor:
`metros + bolsas × 10`. Só o melhor resultado de cada jogador fica no ranking.

| Resposta | Quando |
|---|---|
| `200 {"score","best","record","rank"}` | registrado |
| `400 {"erro":"corrida_impossivel"}` | mais de 28 m/s, bolsas demais para a distância ou < 3 s |
| `403 {"erro":"token_desconhecido"}` | token inválido |
| `429` | mais de 150 envios por hora no mesmo IP |

## `GET /api/top?n=50`

```json
{ "top": [ { "pos": 1, "name": "Isa", "score": 1200, "meters": 800, "souls": 40 } ], "total": 1 }
```

Empate: quem fez primeiro fica na frente. `n` vai de 1 a 100.

## `GET /api/health`

`{"ok": true}`
