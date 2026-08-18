# IVE

Assistente de tarefas digitais para escritório contábil. Um agente com ferramentas:
o modelo **planeja**, o Python **executa**.

Estado atual: **loop + API + interface**, cardápio somente leitura, e o cérebro
trocável entre nuvem e modelo local.

```
Interface (React/TS) ──HTTP──▶ Servidor (FastAPI) ──▶ ive/ ──▶ motor
                                                              ├─ anthropic (nuvem)
                                                              └─ local (Ollama)
```

---

## Instalação (Windows)

```powershell
cd C:\Users\UP\OneDrive\Desktop\.IVE

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

copy .env.example .env
notepad .env          # escolha o motor e preencha o que ele precisa
```

> Se o PowerShell reclamar de execução de script:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

Confira se está de pé:

```powershell
python -m pytest -q          # 34 testes, nenhum gasta API
python main.py --ferramentas # mostra o cardápio
```

## Uso

**Linha de comando:**

```powershell
python main.py                                        # modo conversa
python main.py "quantos clientes tem na planilha de agosto?"
python main.py --historico                            # o que já foi rodado
```

**Interface gráfica** — dois terminais:

```powershell
uvicorn ive.servidor:app --host 127.0.0.1 --port 8010
```

```powershell
cd ui && npm install && npm run dev
```

Abra <http://localhost:5173>.

Pergunte para ele: *"tem algum e-mail duplicado ou faltando na clientes_agosto?"*
A planilha de exemplo tem **um e-mail vazio e um duplicado plantados de propósito** —
serve pra você ver o agente encontrar sozinho.

---

## Como funciona o miolo

```
    você  ──pedido──▶  IVE (loop.py)
                          │
                          ├─▶ motor  ── "quero chamar ler_planilha(...)"
                          │
                          ├─▶ registry.executar()  ──▶  função Python sua
                          │                              (testada, sem IA dentro)
                          │◀── resultado ────────────────┘
                          │
                          └─▶ volta pro motor até ele responder em texto
```

Quatro coisas sustentam isso:

**1. O cardápio é o limite.** `enviar_email` não existe em `ive/tools/` →
é fisicamente impossível o agente enviar e-mail. Não importa o que ele alucine,
o que o prompt peça ou o que esteja escrito dentro de um PDF. Vale igual pela
CLI, pelo modelo local e por rota HTTP — tem teste pros três.

**2. A jaula de caminhos** (`ive/seguranca.py`). O modelo escolhe strings, e string
vira caminho de arquivo. Tudo que toca disco passa por `caminho_seguro()`:
bloqueia `../`, caminho absoluto, symlink pra fora e extensão não permitida.
O agente só enxerga `dados/`.

**3. Sem memória, com log.** O contexto vive dentro de `rodar()` e morre no fim.
Mesma entrada = mesmo comportamento, sempre. Mas o **sistema** grava tudo em
SQLite (`logs/ive.sqlite3`): quem rodou, quando, qual ferramenta, qual resultado.
Isso não é memória da IA, é auditoria — é o que responde
*"esse boleto foi enviado pra quem?"* daqui a três meses.

**4. O cérebro é trocável.** `loop.py` não menciona Claude, Ollama nem HTTP.
Ele fala com um `Motor` (ver `ive/motores/base.py`). Trocar de motor não muda
ferramenta, jaula, log nem interface — é a prova de que a inteligência é uma
peça, não o sistema.

---

## Os dois motores

```powershell
$env:IVE_MOTOR = "local"      # ou "anthropic"
```

| | `anthropic` | `local` |
|---|---|---|
| Onde roda | nuvem | seu PC (Ollama) |
| Custo | por token | zero |
| Internet | obrigatória | dispensável |
| Dados do cliente | saem da máquina | não saem |
| Chamar ferramenta | confiável | **erra bastante** |
| Velocidade sem GPU | — | poucos tokens/s |

O motor local usa Ollama. Instale, deixe rodando, e baixe um modelo:

```powershell
ollama pull qwen3:4b
```

Modelo de 3-4B inventa nome de ferramenta, erra o schema e entra em loop.
O `registry` barra o estrago — ferramenta que não existe não executa — mas o
agente falha mais. Isso é o preço honesto de não depender de API externa.

Na interface dá pra alternar entre os dois **no mesmo pedido**, sem reiniciar nada.

---

## As duas famílias de rota

O ponto de arquitetura mais importante do servidor:

| | Passa pelo modelo | Chamada direta |
|---|---|---|
| Rota | `POST /executar` | `POST /ferramentas/{nome}` |
| Quando | intenção **vaga** | intenção **exata** |
| Exemplo | *"confere os e-mails aí"* | botão "Conferir coluna E-mail" |
| Custo | tokens | zero |
| Velocidade | segundos | instantâneo |

**Passa pelo modelo o que precisa de julgamento. O resto é chamada direta.**
Mandar um clique de botão pra uma IA interpretar é mais lento, mais caro e
pode errar.

Na interface, hoje, só a **caixa de texto** tem gatilho: a chamada direta
existe no `api.ts` (`chamarFerramenta`) e no servidor, mas os botões que a
disparavam saíram da barra lateral — ocupavam a barra inteira e ninguém
usava. A conversa ainda sabe **exibir** uma resposta direta, etiquetada
(`direto · inspecionar_coluna`); o que falta é quem a peça.

---

## Voz

São **dois problemas separados**, e eles não se parecem em nada.

### Falar — `ui/src/voz.ts`

Síntese do próprio Windows via `speechSynthesis`. Zero download, zero
servidor, e o texto não sai da máquina: as vozes reportam
`localService: true`. Em Personalizar dá pra escolher a voz (Daniel ou
Maria), o ritmo, e ligar a fala automática. Cada resposta tem um `▶` no
hover pra ouvir de novo.

O texto é **quebrado em frases** antes de falar. Não é capricho: o Chrome
corta a fala por volta de 15 segundos quando a frase é longa demais.

### Conversa por voz — `ui/src/ModoVoz.tsx` + `ui/src/Esfera.tsx`

O `◎` ao lado da caixa troca a conversa de texto pela de voz. A entrada é
o mesmo arco da logo, mas com a câmera seguindo o ponto:

```
▌·   o "i"
·    o I arma e lança o ponto pra cima
▌    a haste cai e sai de quadro
·    o ponto centraliza, girando rápido
●    explode em esfera pontilhada
```

Tudo num canvas só. Poderia ser DOM na primeira metade e canvas na
segunda, mas seriam dois relógios para sincronizar no instante da
explosão — justamente o momento que precisa ser exato.

**A esfera:** 2600 partículas, direção uniforme na esfera (sorteando `z` e
o ângulo separadamente — sortear dois ângulos concentraria pontos nos
polos) e raio por `cbrt`, que distribui uniforme no *volume*. Projetado em
2D isso já produz o centro brilhante, porque a corda é mais longa no meio.
22% ficam fora da bola formando o halo esfumaçado da borda.

Os pontos fogem do cursor com mola e voltam ao lugar. A esfera pulsa: com o
**seu volume** enquanto você fala, batimento lento enquanto o IVE pensa, e
outro ritmo enquanto ele responde — é o que diz "estou te ouvindo" sem
escrever isso na tela.

Detalhe de desempenho: o gargalo não é o número de pontos, é trocar
`fillStyle` 2600 vezes por quadro. Os pontos são agrupados em 7 baldes de
opacidade, então são 7 trocas de estado.

### Falar — Piper

Rede neural (VITS) rodando aqui. O texto nao sai da maquina.

```
"confere a planilha"  →  eSpeak-ng  →  /kõˈfɛɾi a plɐˈniʎɐ/  →  VITS/ONNX  →  🔊
```

Roda rapido na CPU porque a arquitetura e enxuta e o modelo e executado
pelo onnxruntime — o mesmo que ja estava aqui por causa do Whisper.

**Medido nesta maquina (i3, sem GPU):**

| texto | audio gerado | tempo | fator |
|---|---|---|---|
| 7 car. | 0,48 s | 0,38 s | 1,2x |
| 49 car. | 2,47 s | 0,51 s | 4,8x |
| 97 car. | 5,84 s | 0,78 s | **7,5x** |

Ha um custo fixo de ~0,3 s por chamada; frase longa dilui. Por isso o
`voz.ts` quebra o texto em frases e **busca a proxima enquanto a atual
toca** — sem esse adiantamento, cada frase pagaria a latencia de novo.

**Duas vozes no seletor**, uma de cada motor. E o seletor mostra so
**"Masculina" e "Feminina"** — nome proprio de voz interessa a quem monta
a voz, nao a quem escolhe uma. Os arquivos em disco mantem os nomes.

Medido nesta maquina com a MESMA frase (~4 s de audio), modelo ja quente:

| no seletor | arquivo | motor | sintese | fator |
|---|---|---|---|---|
| **Masculina** | `pt_BR-faber-medium` | piper | **0,23 s** | **16,5x** |
| Feminina | `pf_bella` | kokoro | 16,5 s | 0,26x |

### A voz feminina e montada

**Nao existe voz feminina em portugues no Piper.** As quatro (cadu,
edresson, faber, jeff) sao masculinas e de locutor unico; nao ha modelo
multi-locutor em pt no catalogo. O Kokoro tem tres em pt e so a `pf_dora`
e feminina. Esse e o catalogo inteiro de voz local em pt-BR — e a Dora
sozinha nao passava no ouvido.

A saida veio em dois niveis. Vale ler os dois: **o primeiro nao resolve
sem o segundo.**

**Nivel 1 — o vetor de estilo tem duas metades.** O Kokoro e StyleTTS2, e
os 256 numeros do vetor nao sao um bloco so: a primeira metade alimenta o
decodificador (o TIMBRE) e a segunda alimenta o preditor de duracao e F0
(o RITMO e a entonacao, que e onde mora o sotaque). Medido trocando as
metades e cronometrando a saida:

| vetor | duracao | F0 |
|---|---|---|
| af_bella | 7,88 s | 205 Hz |
| pf_dora | 6,22 s | 175 Hz |
| 1a bella + 2a dora | **6,22 s** | **180 Hz** |
| 1a dora + 2a bella | 7,88 s | 195 Hz |

Duracao e pitch seguem a segunda metade, exatamente. Entao da pra costurar
o timbre de uma no ritmo da outra — e e isso que a `pf_bella` e:

```python
nova = bella.copy()
nova[:, :, 128:] = dora[:, :, 128:]   # timbre da Bella, ritmo da Dora
```

Somar os vetores INTEIROS (`bella * 0.5 + dora * 0.5`), que foi a primeira
tentativa, borra as duas coisas juntas: perde timbre pra ganhar ritmo. A
metade a metade nao tem esse compromisso.

**Nivel 2 — os fonemas.** O eSpeak escreve o portugues com simbolos que a
Dora viu em treino e a Bella nunca. Pra ela cada um aponta pro som INGLES:

```
planilha   plˌænˈiljæ     "lh" vira l+j ("planilhia"), e o final e o [æ] de "cat"
tres       trˈes          r comum, quando em pt e TAP
carro      kˈaxʊ          [x] nao existe em ingles
porta      pˈɔɾətæ        o espeak enfia um schwa: "po-ro-ta"
```

O conserto e reescrever a fonemizacao com simbolos cuja leitura inglesa
cai no som certo — o `ɾ` que ela conhece do "butter" americano e o mesmo
tap do "tres". A lista mora em `_CONSERTOS`, no `fala.py`, e e **amarrada
a voz** (`_TIMBRE_ESTRANGEIRO`): numa voz nativa o mesmo conserto
estragaria a fala.

> **Correcao de um diagnostico errado que ficou aqui por semanas.** Este
> README dizia que o til combinante U+0303 nao estava no vocabulario do
> tokenizador, e que era por isso que "nao" e "entao" saiam tortos. Fomos
> conferir: **U+0303 esta no vocabulario**, e na frase de teste inteira
> nenhum fonema e descartado. A causa era outra — a de cima.

Candidatas ja baixadas ficam em `vozes/kokoro/candidatas/` — em disco, mas
fora do seletor. **Adicionar uma voz e mover o arquivo uma pasta pra cima:**

```
mv vozes/kokoro/candidatas/af_heart.bin vozes/kokoro/
```

O `fala.py` varre `.bin` soltos, entao nao ha nada pra reempacotar. A 2a
letra do nome diz o genero (`af_` = feminina americana, `bf_` = britanica,
`pf_` = portuguesa) — e e so isso que o seletor precisa saber.

### O preco da voz feminina

Ela custa **~70x** o Faber pra dizer a mesma frase: 16,5 s contra 0,23 s.
A interface avisa ao escolher.

Este numero corrige o que estava aqui antes (0,8x de fator, "20x mais
lento"). Aquilo vinha de uma medicao com frase curta e modelo recem-usado;
repetida quatro vezes com a mesma frase, a taxa fica em 0,26x — estavel, e
sem diferenca perceptivel com ou sem o servidor de desenvolvimento junto.

Onde ela serve: **frase curta, e audio gerado uma vez e guardado.**
Saudacoes e confirmacoes sao um conjunto pequeno e finito — a lentidao nao
importa quando acontece so uma vez.

Duas notas de implementacao que custaram tempo:
- O modelo `q8f16` do Kokoro **derruba o onnxruntime com segfault** nesta
  maquina. Usamos o `model_quantized` (int8 puro).
- O `kokoro-onnx` 0.4.7 manda `speed` como `int32` num modelo que declara
  `float`. Chamamos a sessao ONNX direto, com o tipo certo.

Os modelos ficam em `vozes/`, fora do git. **Nao** em `dados/` — aquilo e a
jaula do agente, e modelo de voz nao e dado de cliente. Para rebaixar uma
voz do Piper:

```
python -m piper.download_voices pt_BR-jeff-medium --download-dir vozes
```

As frases que cada voz diz ao ser testada moram em **`ui/src/frases.ts`** —
um arquivo so pra isso. O botao fala exatamente o que estiver escrito la,
sem rodizio nem surpresa.

> **A voz do Windows foi removida.** Ela era concatenativa: pedacos de
> audio gravados e costurados, tecnologia dos anos 90. Nao havia ajuste que
> resolvesse o timbre robotico; era o metodo.

### Ouvir — `ive/voz.py` + `POST /voz/ouvir`

Whisper rodando aqui, via `faster-whisper`, modelo `small` em int8.
**O áudio não sai do PC** — num escritório contábil isso não é preferência,
é requisito: a gravação tem nome de cliente, CNPJ e valor. É exatamente por
isso que a API de fala do Chrome está fora: ela manda o áudio pro Google.

**Push-to-talk**, não "sempre ouvindo". O microfone abre só enquanto o botão
está pressionado, e as faixas são liberadas no `onstop`. Decisão de
privacidade, não de tecnologia — microfone aberto num escritório onde se
conversa com cliente é risco que nenhuma conveniência paga.

O texto transcrito vai pra **caixa de texto**, não direto pro agente.
Transcrição errada vira ação errada.

Medido nesta máquina (i3 sem GPU), com áudio de 6,45 s:

| formato | tempo | tamanho |
|---|---|---|
| WAV | 5,9 s (1ª, carrega o modelo) | 278 KB |
| webm/opus (o que o navegador manda) | 4,4 s | 55 KB |

Transcrição bateu palavra por palavra com o falado, confiança 0,82.

> **Voz não é ferramenta e não entra no `registry`.** O cardápio é o que o
> *modelo* pode pedir. Se `falar()` ou `ouvir()` virassem ferramenta, o
> modelo poderia decidir sozinho abrir a caixa de som ou ligar o microfone
> do escritório. Voz é decisão da **interface**. Essa separação é o que
> mantém a garantia "o cardápio é o limite físico" valendo inteira.

Não vai usar voz? Tire `faster-whisper` do `requirements.txt` — o resto
funciona sem, e o botão de microfone some sozinho se o navegador não
oferecer captura.

## Tema

Você escolhe **uma** cor — o fundo. Todo o resto obedece.

Não existe "tema claro" e "tema escuro" como código separado. Existe
`ui/src/tema.ts`, que calcula a **luminância** do fundo e decide a cor do
texto; e o `estilo.css`, onde painel, borda e tons secundários saem de
`color-mix()` entre esses dois. Trocar o fundo repinta a interface inteira
sem ninguém manter uma lista de cores por tema.

A virada entre texto claro e escuro é **0,179** — o ponto onde o contraste
com branco iguala o contraste com preto. Sai de resolver
`(L+0,05)² = 1,05 × 0,05`, não é chute.

Uma coisa que a medição pegou: **a mesma proporção de mistura não serve
para os dois lados.** Luminância não é linear, e misturar branco em direção
a um fundo branco perde contraste muito mais rápido. Com proporção única, os
tons secundários caíam para 2,3:1 nos temas claros — ilegível. Por isso o
`tema.ts` escreve `--mix-fraco` e `--mix-apagado` diferentes conforme o caso.

Resultado medido nos 8 temas, pior caso de cada nível:

| nível | pior contraste | AA pede |
|---|---|---|
| texto | 13,87 | 4,5 |
| fraco | 7,16 | 4,5 |
| apagado | 4,80 | 4,5 |
| acento | 5,05 | 4,5 |

A escolha fica no `localStorage` e é aplicada **antes** do primeiro render,
senão a tela pisca na cor padrão.

## A marca

**Logo principal: `I.V.E`.** **Marca simples: só o `i`** — para favicon,
cabeçalho apertado e qualquer lugar onde a palavra inteira não caiba.

O conceito da animação: o pingo quadrado do **i** é a flecha e a haste é o
arco. Ela encolhe pra armar, estica de volta e lança o quadrado, que gira
uma volta e cai virando o **primeiro ponto de I.V.E** — enquanto a haste
vira o **I** maiúsculo e o V e o E entram pela esquerda.

Ela toca como **inicialização** ao abrir o sistema, e depois entrega a tela.
Clicar pula. Só aparece uma vez por aba, senão o Vite a repetiria a cada
arquivo salvo.

```
ui/src/logo.css     os keyframes — desenho original, intacto
ui/src/Logo.tsx     <LogoIVE> e <LogoMarca> + a medição
ui/public/favicon.svg
```

Duas decisões que valem saber:

**As medidas não estão chumbadas.** O `Logo.tsx` mede o glifo `I` da fonte
real num canvas e escreve as variáveis CSS. A barra tem exatamente a
espessura do I em qualquer tamanho, e nada entorta se a fonte demorar a
carregar.

**A abertura anda pelo relógio da animação, não pelo relógio de parede.**
Navegador congela animação CSS em página oculta, mas `setTimeout` continua
correndo — com timers, abrir o app numa aba em segundo plano fazia a
abertura terminar sem nunca ter animado. `requestAnimationFrame` congela
junto com a animação, então os dois concordam.

**A fonte é uma variável só.** `--fonte-logo` no `estilo.css` + o `<link>` no
`index.html`. Compare as opções lado a lado abrindo `/fontes.html` com a UI
no ar — a página monta cada fonte com a mesma construção da logo real (barra
e quadrado desenhados, só o V e o E vindos da fonte), então a comparação é
justa. Hoje: **Anton**.

> ⚠️ **A fonte vem do Google Fonts**, ou seja, é um pedido para a internet.
> Com o motor local o IVE roda offline e a logo cai no fallback do sistema.
> Para fechar isso, baixe o `.woff2` para `ui/public/fontes/` e troque o
> `<link>` por um `@font-face`.

> ⚠️ **Não chame nada de `.barra` no CSS de layout.** Já aconteceu: a barra
> lateral usava esse nome, e o `border-radius: 14px` dela vazou para dentro
> da marca, arredondando o I e um dos pontos. As peças da logo agora são
> `.tira`, e o `logo.css` zera raio/borda/padding explicitamente.

## Estrutura

```
.IVE/
├── main.py                  CLI
├── ive/
│   ├── config.py            motor, chaves, pastas, prompt de sistema
│   ├── loop.py              ⭐ o loop do agente (não sabe quem pensa)
│   ├── servidor.py          FastAPI — a costura com a interface
│   ├── registry.py          o cardápio (@ferramenta)
│   ├── seguranca.py         jaula de caminhos
│   ├── logdb.py             auditoria SQLite
│   ├── motores/
│   │   ├── base.py          o contrato Motor
│   │   ├── nuvem.py         Anthropic
│   │   └── local.py         Ollama
│   └── tools/
│       ├── planilha.py      ler_planilha, inspecionar_coluna, filtrar_planilha
│       └── arquivos.py      listar_arquivos, extrair_texto_pdf, extrair_cnpj_do_pdf
├── ui/                      interface React + TypeScript (Vite)
│   ├── src/api.ts           cliente tipado — o React Native reaproveita inteiro
│   ├── src/Logo.tsx         marca I.V.E + marca simples "i" + abertura
│   └── src/logo.css         a animação do arco
├── dados/                   ⚠️ único lugar que o agente enxerga
├── logs/                    banco de auditoria (fora do git)
└── tests/                   34 testes, nenhum gasta API
```

### Onde este repositório fica

Ele é uma das duas pastas dentro de `.IVE/`, que não é repositório nenhum —
é só a gaveta que guarda as duas:

```
.IVE/
├── project-ive/        este repositório — o motor e o produto
└── landing-page-ive/   a vitrine, repositório separado
```

As três partes têm papéis separados e nenhuma importa código da outra:

| pasta                       | o que é   | como vive               |
| --------------------------- | --------- | ----------------------- |
| `project-ive/ive/`          | o motor   | Python, este repo       |
| `project-ive/ui/`           | o produto | Vite + React, este repo |
| `landing-page-ive/`         | a vitrine | Next.js, repo separado  |

**O contrato entre a vitrine e o produto é uma URL, e só.** A landing tem
uma caixa igual à do app; ao enviar, ela navega para
`NEXT_PUBLIC_IVE_URL/?q=<pergunta>`. Deste lado, `ui/src/App.tsx` lê o `?q=`,
preenche a caixa, põe o cursor no fim e apaga o parâmetro da URL — sem isso
um F5 ressuscitaria a pergunta antiga por cima do que a pessoa escreveu.

Ela não envia sozinha: execução custa token e o servidor pode estar fora do
ar, então quem aperta enter é a pessoa.

Se mexer no formato desse parâmetro, os dois repositórios precisam mudar
juntos — é o único ponto onde eles se tocam.

## Adicionar uma ferramenta

```python
# ive/tools/minha_coisa.py
from ..registry import ferramenta
from ..seguranca import caminho_seguro

@ferramenta(
    nome="contar_paginas_pdf",
    descricao="Conta quantas páginas tem um PDF.",  # o modelo LÊ isto — capriche
    schema={
        "type": "object",
        "properties": {"caminho": {"type": "string", "description": "Nome do PDF"}},
        "required": ["caminho"],
    },
)
def contar_paginas_pdf(caminho: str) -> dict:
    import pdfplumber
    with pdfplumber.open(caminho_seguro(caminho)) as pdf:
        return {"paginas": len(pdf.pages)}
```

Depois registre em `ive/tools/__init__.py`. Só isso — ela aparece nos dois
motores, na CLI, na API e na interface automaticamente.

A `descricao` é prompt, não comentário. Ferramenta que o modelo usa errado
quase sempre é descrição ruim, não modelo burro. Com modelo local isso pesa
ainda mais.

---

## Roadmap

- [x] **Semana 1** — loop + primeira ferramenta de leitura
- [x] **Semana 2** — mais leitura: PDF, listagem, inspeção de coluna
- [x] **API + interface** — FastAPI, React/TS, duas famílias de rota
- [x] **Motor trocável** — nuvem ou modelo local, sem mudar mais nada
- [ ] **Semana 3** — primeira ferramenta de **escrita**, com portão de aprovação.
      `enviar_email` **não envia**: grava numa fila. A tela mostra os N destinatários
      (nome / e-mail / PDF anexo / valor), o humano confere e clica. Só então dispara.
- [x] **Voz** — falar (síntese do Windows) e ouvir (Whisper local,
      push-to-talk). Camada de fora: o `loop.py` não mudou uma linha.
- [ ] **Memória** — transformar o `logdb` em memória de verdade: recuperação
      semântica e consolidação. É a versão viável da tese de aprendizado contínuo,
      e não precisa de GPU nem de treinar modelo.
- [x] **Piper** — voz neural local, 6x mais rápida que tempo real na CPU.
- [ ] **Voz própria** — clonagem (XTTS-v2 / F5-TTS) para uma voz que seja
      só do IVE. Roda, mas é lento demais sem GPU; fica para quando houver.
- [ ] Depois — React Native apontando pro mesmo servidor

### Antes da Semana 3, decidir

Envio de boleto é dinheiro. Dois riscos concretos:

1. **Troca de destinatário.** Uma linha deslocada e o boleto do cliente A vai pro
   e-mail do cliente B — com CNPJ e valor expostos. Isso é incidente de LGPD.
   Por isso `extrair_cnpj_do_pdf` existe: o casamento PDF↔cliente é por **CNPJ
   extraído do próprio PDF**, nunca por posição de linha ou nome de arquivo.
   Se não bater, falha explícita — não manda.
2. **Boleto por e-mail é vetor clássico de fraude no Brasil.** Padronizar remetente,
   colocar os dados de conferência no corpo (valor, vencimento, beneficiário) e,
   se der, um canal alternativo de verificação.

E antes de tudo isso: **de onde vêm os PDFs dos boletos?** Pasta, e-mail ou API
do banco — cada resposta gera um desenho diferente.

---

## Segurança

- `.env` está no `.gitignore`. **Nunca** commite sua chave de API.
- `dados/` também está ignorado (só a planilha de exemplo vai pro git) —
  dado de cliente real não sobe pro GitHub.
- O servidor escuta **só em 127.0.0.1** e **não tem autenticação**. Ele não é
  um servidor de internet. No dia que virar app de celular, isso muda: os dados
  passam a trafegar pela rede, e aí entram autenticação, TLS e LGPD.
- Rode `python -m pytest -q` antes de todo commit.
