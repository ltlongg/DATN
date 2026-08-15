# Tai lieu tham khao Chonkie cho RAG/chunking

Ngay tong hop: 2026-06-11

Nguon chinh:

- Quick Start: https://docs.chonkie.ai/oss/quick-start
- Docs index: https://docs.chonkie.ai/llms.txt
- Installation: https://docs.chonkie.ai/oss/installation
- Pipelines: https://docs.chonkie.ai/oss/pipelines
- Chunkers Overview: https://docs.chonkie.ai/oss/chunkers/overview
- Token Chunker: https://docs.chonkie.ai/oss/chunkers/token-chunker
- Sentence Chunker: https://docs.chonkie.ai/oss/chunkers/sentence-chunker
- Recursive Chunker: https://docs.chonkie.ai/oss/chunkers/recursive-chunker
- Semantic Chunker: https://docs.chonkie.ai/oss/chunkers/semantic-chunker
- Embeddings Overview: https://docs.chonkie.ai/oss/embeddings/overview

## 1. Chonkie la gi?

Chonkie la thu vien ingestion/chunking cho cac pipeline RAG. Trong RAG, chat luong chunk anh huong truc tiep den retrieval: chunk qua ngan thi mat ngu canh, chunk qua dai thi nhieu nhieu va ton context. Chonkie tap trung vao viec chia van ban thanh cac don vi nho hon bang nhieu chien luoc khac nhau: chia theo token, cau, cau truc tai lieu, do tuong dong ngu nghia, code AST, bang, hoac qua mo hinh LLM/Genie.

Y tuong su dung co ban:

```python
from chonkie import TokenChunker

chunker = TokenChunker()
chunks = chunker("Noi dung can chia...")

for chunk in chunks:
    print(chunk.text)
    print(chunk.token_count)
```

Moi chunk thuong la mot object co cac truong quan trong:

- `text`: noi dung chunk.
- `start_index`: vi tri bat dau trong van ban goc.
- `end_index`: vi tri ket thuc trong van ban goc.
- `token_count`: so token theo tokenizer/counter duoc cau hinh.
- `context`: ngu canh bo sung neu dung refinery overlap.
- `embedding`: vector embedding neu dung embeddings/refinery.

## 2. Cau truc tai lieu chinh cua Chonkie

Theo `llms.txt`, docs Chonkie hien co cac nhom kien thuc lon sau:

1. Getting Started

   Gom Quick Start, Installation va Pipelines. Day la phan nen tang de cai dat, chay thu chunker va lap pipeline xu ly tai lieu.

2. API Server

   Chonkie co the duoc self-host thanh REST API. Phan nay gom Overview, Quick Start, Endpoints, Pipeline va Docker. No huu ich neu muon mot service chunking ngon ngu doc lap, vi du backend Python goi API thay vi import truc tiep.

3. Chefs

   Chefs la lop tien xu ly dau vao thanh `Document` hoac cau truc trung gian de chunk. Cac chef chinh:

   - `TextChef`: xu ly plain text.
   - `MarkdownChef`: xu ly Markdown, co y thuc ve table, code block, image.
   - `TableChef`: trich xuat/chuan bi bang tu Markdown/HTML table.
   - `MistralOCR`: trich xuat text tu anh/PDF bang Mistral OCR API.

4. Fetchers

   Fetchers lay du lieu tu nguon. Hien docs noi ro `FileFetcher` de doc file hoac thu muc trong local filesystem.

5. Chunkers

   Day la phan quan trong nhat cho RAG. Chonkie co nhieu chunker:

   - `TokenChunker`
   - `SentenceChunker`
   - `RecursiveChunker`
   - `SemanticChunker`
   - `CodeChunker`
   - `TableChunker`
   - `FastChunker`
   - `LateChunker`
   - `NeuralChunker`
   - `SlumberChunker`
   - `TeraflopAIChunker`

6. Embeddings

   Chonkie cung cap wrapper thong nhat cho nhieu embedding provider: Auto, Model2Vec, SentenceTransformer, OpenAI, Azure OpenAI, Cohere, Gemini, Jina, VoyageAI va custom embeddings.

7. Refinery

   Refinery hau xu ly chunks. Hai refinery quan trong:

   - `OverlapRefinery`: them ngu canh overlap tu chunk lien ke.
   - `EmbeddingsRefinery`: gan embedding vao chunk.

8. Handshakes

   Handshakes day chunks sang vector databases/search engines:

   - Chroma
   - Qdrant
   - Pinecone
   - Weaviate
   - Milvus
   - LanceDB
   - MongoDB
   - Elasticsearch
   - PostgreSQL pgvector
   - Turbopuffer

9. Porters

   Porters export chunks ra dinh dang khac:

   - `JSONPorter`: export JSON.
   - `DatasetsPorter`: export Hugging Face Dataset.

10. Utils

    Gom Visualizer, Hubbie va Logging.

11. Experimental va Deprecated

    Experimental gom CLI va experimental Code Chunker. Deprecated gom SDPM Chunker legacy, hien da duoc tich hop/ke thua boi SemanticChunker voi `skip_window`.

## 3. Cai dat

### 3.1. Cai dat Python co ban

```bash
pip install chonkie
```

Ban co ban phu hop cho cac nhu cau chia van ban don gian, gom cac chunker nhu Token, Sentence va Recursive.

### 3.2. Cai dat day du

```bash
pip install "chonkie[all]"
```

Ban `all` cai them gan nhu tat ca tinh nang nang cao: semantic, code, neural, genie, visualization, embeddings providers, v.v.

### 3.3. Cac extras dang chu y

```bash
pip install "chonkie[hub]"
pip install "chonkie[viz]"
pip install "chonkie[semantic]"
pip install "chonkie[openai]"
pip install "chonkie[cohere]"
pip install "chonkie[jina]"
pip install "chonkie[st]"
pip install "chonkie[code]"
pip install "chonkie[neural]"
pip install "chonkie[genie]"
pip install "chonkie[groq]"
pip install "chonkie[cerebras]"
```

Ghi chu:

- `semantic`: cai provider semantic mac dinh, hien la Model2Vec.
- `openai`: cai OpenAI embeddings va tokenizer lien quan.
- `st`: cai SentenceTransformer, can cho mot so truong hop nhu LateChunker.
- `code`: cai tree-sitter va cac goi lien quan de chunk code.
- `neural`: cai transformers/torch cho NeuralChunker.
- `genie`: dung cho SlumberChunker/LLM interface.

### 3.4. JavaScript

```bash
npm install @chonkiejs/core
npm install @chonkiejs/token
npm install @chonkiejs/cloud
```

`@chonkiejs/core` dung cho local chunking. `@chonkiejs/token` dung khi can custom tokenizer. `@chonkiejs/cloud` dung khi goi API.

### 3.5. Logging

Chonkie dieu khien logging bang bien moi truong `CHONKIE_LOG`:

```bash
export CHONKIE_LOG=off
export CHONKIE_LOG=warning
export CHONKIE_LOG=info
export CHONKIE_LOG=debug
```

Mac dinh la warning/errors.

## 4. Interface chung cua chunkers

Chonkie co interface kha dong nhat giua cac chunker:

```python
chunks = chunker.chunk(text)
batch_chunks = chunker.chunk_batch(texts)
chunks = chunker(text)
batch_chunks = chunker([text1, text2])
```

Async:

```python
chunks = await chunker.achunk(text)
batch_chunks = await chunker.achunk_batch(texts)
doc = await chunker.achunk_document(doc)
```

Theo docs, async support co san trong chunkers va dung `asyncio.to_thread` de tranh block event loop. Dieu nay co loi khi dung trong FastAPI, Starlette, aiohttp, Sanic, Litestar, v.v.

## 5. TokenChunker

### 5.1. Muc dich

`TokenChunker` chia van ban thanh cac chunk co kich thuoc token co dinh, co the cau hinh overlap. Day la chien luoc don gian, de du doan, phu hop khi muc tieu chinh la khong vuot qua token budget cua embedding model hoac LLM.

### 5.2. Cai dat

`TokenChunker` co trong ban cai dat co ban:

```bash
pip install chonkie
```

### 5.3. Tham so quan trong

- `tokenizer`: tokenizer/counter. Co the la `"character"`, `"word"`, `"byte"`, `"gpt2"` hoac tokenizer instance.
- `chunk_size`: so token toi da moi chunk.
- `chunk_overlap`: so token hoac ty le overlap giua cac chunk.

### 5.4. Vi du

```python
from chonkie import TokenChunker

chunker = TokenChunker(
    tokenizer="gpt2",
    chunk_size=512,
    chunk_overlap=50,
)

chunks = chunker.chunk(long_text)

for chunk in chunks:
    print(chunk.text)
    print(chunk.token_count)
    print(chunk.start_index, chunk.end_index)
```

### 5.5. Khi nao nen dung

Nen dung khi:

- Can kich thuoc chunk deu.
- Can dam bao chunk khong vuot token limit.
- Tai lieu khong co cau truc ro hoac chat luong semantic boundary khong qua quan trong.

Khong ly tuong khi:

- Tai lieu co heading/section ro rang.
- Can giu tron y theo doan/cau.
- Noi dung co nhieu chu de xen ke va can grouping ngu nghia.

## 6. SentenceChunker

### 6.1. Muc dich

`SentenceChunker` chia van ban theo ranh gioi cau, giup chunk khong bi cat ngang cau. Dieu nay thuong tot hon `TokenChunker` khi du lieu la van ban tu nhien, vi moi chunk giu duoc cau hoan chinh.

### 6.2. Cai dat

Co trong ban cai dat co ban:

```bash
pip install chonkie
```

### 6.3. Tham so quan trong

- `tokenizer`: tokenizer/counter.
- `chunk_size`: token toi da moi chunk.
- `chunk_overlap`: overlap token giua chunks.
- `min_sentences_per_chunk`: so cau toi thieu trong chunk.
- `min_characters_per_sentence`: loc cac cau/fragment qua ngan.
- `delim`: delimiter de tach cau, vi du `.`, `!`, `?`, `\n`.
- `include_delim`: delimiter gan voi cau truoc hay cau sau.

### 6.4. Vi du

```python
from chonkie import SentenceChunker

chunker = SentenceChunker(
    tokenizer="character",
    chunk_size=2048,
    chunk_overlap=128,
    min_sentences_per_chunk=1,
)

chunks = chunker.chunk(text)
```

### 6.5. Khi nao nen dung

Nen dung khi:

- Tai lieu la van ban tu nhien.
- Muon tranh cat cau.
- Heading/paragraph khong quan trong bang su tron ven cau.

Luu y voi tieng Viet:

- Dau cham trong viet tat, danh sach, ngay thang co the gay tach cau sai.
- Can cau hinh delimiter can than neu tai lieu co nhieu bullet/list.

## 7. RecursiveChunker

### 7.1. Muc dich

`RecursiveChunker` chia tai lieu theo cac muc delimiter/rule tu lon den nho. No phu hop voi tai lieu dai nhung co cau truc ro, vi du sach, paper, tai lieu Markdown, van ban phap ly, giao trinh.

Khac voi `TokenChunker`, RecursiveChunker co gang ton trong cau truc tai lieu truoc, roi chi tach nho khi mot phan vuot `chunk_size`.

### 7.2. Cai dat

Co trong ban cai dat co ban:

```bash
pip install chonkie
```

### 7.3. Tham so quan trong

- `tokenizer`: tokenizer/counter.
- `chunk_size`: token toi da moi chunk.
- `rules`: `RecursiveRules`, gom nhieu `RecursiveLevel`.
- `min_characters_per_chunk`: chunk qua ngan se duoc xu ly/gom theo logic cua chunker.

### 7.4. Rules

Theo docs, `RecursiveChunker` dung `RecursiveRules` va `RecursiveLevel` de xac dinh cac bac tach.

Y tuong:

```python
from chonkie import RecursiveChunker
from chonkie.types import RecursiveLevel, RecursiveRules

rules = RecursiveRules(
    levels=[
        RecursiveLevel(delimiters=["\n\n"]),
        RecursiveLevel(delimiters=["\n"]),
    ]
)

chunker = RecursiveChunker(
    tokenizer=my_token_counter,
    chunk_size=512,
    rules=rules,
    min_characters_per_chunk=80,
)
```

Trong cau hinh tren:

- Bac 1 tach theo paragraph (`\n\n`).
- Bac 2 tach theo line (`\n`).
- Khong tach tiep xuong cau/tu neu khong them level khac.

Day la cau hinh gan voi code hien tai trong `llm_chunker.py`:

```python
def _chonkie_token_counter(text: str) -> int:
    return count_tokens(text)

@lru_cache(maxsize=4)
def _section_chunker(max_tokens: int, min_chars: int):
    from chonkie import RecursiveChunker
    from chonkie.types import RecursiveLevel, RecursiveRules

    rules = RecursiveRules(
        levels=[
            RecursiveLevel(delimiters=["\n\n"]),
            RecursiveLevel(delimiters=["\n"]),
        ]
    )
    return RecursiveChunker(
        tokenizer=_chonkie_token_counter,
        chunk_size=max_tokens,
        rules=rules,
        min_characters_per_chunk=min_chars,
    )
```

### 7.5. Recipe

Docs noi co the dung recipe co san:

```python
from chonkie import RecursiveChunker

chunker = RecursiveChunker.from_recipe("markdown", lang="en")
chunker = RecursiveChunker.from_recipe(lang="hi")
```

Recipe hien duoc ghi chu la Python only.

### 7.6. Khi nao nen dung

Nen dung khi:

- Tai lieu co section, heading, paragraph, line.
- Muon chunk ton trong cau truc tai lieu.
- Dang xu ly Markdown/tai lieu do an/tai lieu lich su co muc luc va tieu de.

Voi du lieu tieng Viet trong project, RecursiveChunker la lua chon rat hop ly neu pipeline da co `heading_parser.py` va chunk theo section truoc.

## 8. SemanticChunker

### 8.1. Muc dich

`SemanticChunker` chia van ban dua tren do tuong dong ngu nghia. Muc tieu la giu cac noi dung lien quan trong cung chunk va tach khi chu de thay doi.

Docs noi chunker nay co cac tinh nang nang cao:

- Savitzky-Golay filtering de lam muot tin hieu similarity va phat hien boundary on dinh hon.
- Skip-window merging de noi cac nhom lien quan nhung khong nam lien tiep.

### 8.2. Cai dat

```bash
pip install "chonkie[semantic]"
```

### 8.3. Tham so quan trong

- `embedding_model`: string model id hoac object embeddings.
- `threshold`: nguong similarity tu 0 den 1.
- `chunk_size`: token toi da.
- `similarity_window`: so cau dung khi tinh similarity.
- `min_sentences_per_chunk`: so cau toi thieu.
- `min_characters_per_sentence`: loc sentence fragment qua ngan.
- `skip_window`: so nhom co the bo qua de merge noi dung lien quan khong lien tiep.
- `filter_window`: window length cho Savitzky-Golay filter.
- `filter_polyorder`: bac da thuc cua filter.
- `filter_tolerance`: do nhay khi phat hien boundary.
- `delim`: delimiter tach cau.
- `include_delim`: delimiter di voi cau truoc hay cau sau.

### 8.4. Vi du co ban

```python
from chonkie import SemanticChunker

chunker = SemanticChunker(
    embedding_model="minishlab/potion-base-32M",
    threshold=0.7,
    chunk_size=512,
)

chunks = chunker.chunk(text)
```

### 8.5. Y nghia threshold

Theo docs:

- Threshold thap tao chunk lon hon, gom noi dung da dang hon.
- Threshold cao tao chunk nho hon, tap trung chu de hon.

Can test thuc nghiem voi corpus tieng Viet. Mot nguong 0.7-0.8 co the la diem bat dau, nhung khong nen xem la mac dinh toi uu.

### 8.6. Skip-window merging

`skip_window > 0` giup merge cac nhom co lien quan ngu nghia nhung bi chen giua boi noi dung khac.

Huu ich cho:

- Tai lieu co chu de xen ke.
- Tai lieu ky thuat co noi dung lien quan nam rai rac.
- Noi dung co recurring themes.

Vi du:

```python
chunker = SemanticChunker(
    embedding_model="minishlab/potion-base-32M",
    threshold=0.65,
    chunk_size=512,
    skip_window=2,
)
```

### 8.7. Custom embeddings

```python
from chonkie import SemanticChunker
from chonkie.embeddings import AutoEmbeddings

embeddings = AutoEmbeddings.get_embeddings(
    model="sentence-transformers/all-MiniLM-L6-v2"
)

chunker = SemanticChunker(
    embedding_model=embeddings,
    threshold=0.8,
    chunk_size=512,
)
```

Hoac dung OpenAI:

```python
from chonkie import SemanticChunker
from chonkie.embeddings import OpenAIEmbeddings

openai_embeddings = OpenAIEmbeddings(
    model="text-embedding-ada-002"
)

chunker = SemanticChunker(
    embedding_model=openai_embeddings,
    threshold=0.75,
    chunk_size=1024,
)
```

### 8.8. Luu y cho tieng Viet

SemanticChunker phu thuoc manh vao embedding model. Neu model embedding khong manh voi tieng Viet, semantic boundary co the kem on dinh. Voi project tieng Viet, can uu tien:

- Embedding da ho tro multilingual/Vietnamese.
- Test retrieval bang query tieng Viet that.
- So sanh voi RecursiveChunker lam baseline.

## 9. CodeChunker

`CodeChunker` chia code dua tren cau truc code/AST. Phu hop khi ingest repository source code vao RAG. Theo docs, ban Python can extra:

```bash
pip install "chonkie[code]"
```

Nen dung khi:

- Ingest file `.py`, `.ts`, `.js`, v.v.
- Muon giu function/class/block logic thay vi cat theo token.

Khong nen dung cho van ban Markdown/thesis/trich luc lich su.

## 10. TableChunker

`TableChunker` chia bang Markdown hoac HTML table thanh cac chunk nho theo dong, dong thoi giu header. Huu ich khi tai lieu co bang du lieu dai, vi cat bang bang TokenChunker/RecursiveChunker co the lam mat header hoac lam hang bi roi ngu canh.

Nen dung khi:

- Tai lieu co nhieu bang.
- Retrieval can tra loi dua tren dong/cot.
- Bang qua dai so voi token budget.

## 11. FastChunker

`FastChunker` la chunker SIMD-accelerated, chia theo byte va dat muc throughput rat cao theo docs. No hop voi pipeline cuc lon, noi byte-size limit chap nhan duoc.

Danh doi:

- Rat nhanh.
- Nhung boundary co the khong dep ve mat ngu nghia.

## 12. NeuralChunker

`NeuralChunker` dung BERT fine-tuned de phat hien semantic shifts. No huong den chunk theo thay doi chu de. Can extra `neural`, keo theo transformers va torch.

Nen can nhac khi:

- Muon boundary semantic nhung khong chi dua vao similarity heuristic.
- Chap nhan chi phi model nang hon.

## 13. LateChunker

`LateChunker` duoc mo ta la dung Late Chunking algorithm, huu ich cho recall cao hon trong RAG. Thuong lien quan den embedding/context duoc xu ly theo cach tranh mat ngu canh som.

Can doc sau hon neu project can toi uu retrieval recall va co du tai nguyen test.

## 14. SlumberChunker

`SlumberChunker` la agentic chunking dung generative models thong qua Genie interface. Docs goi day la chunking chat luong cao, nhung doi lai chi phi/latency cao hon.

Nen can nhac khi:

- Tai lieu kho, can chunk theo y nghia thay vi rule.
- So luong tai lieu khong qua lon.
- Co ngan sach goi model.

Khong phu hop neu:

- Can ingestion offline nhanh.
- Corpus lon.
- Can deterministic/reproducible cao.

## 15. Embeddings

Chonkie cung cap embeddings handlers voi interface chung:

```python
emb = embeddings.embed(text)
embs = embeddings.embed_batch(texts)
emb = embeddings(text)
embs = embeddings([text1, text2])
```

Provider chinh:

- `AutoEmbeddings`: tu chon handler phu hop.
- `Model2VecEmbeddings`: default trong cai dat `semantic`.
- `SentenceTransformerEmbeddings`: dung sentence-transformers.
- `OpenAIEmbeddings`: dung OpenAI embeddings.
- `AzureOpenAIEmbeddings`: dung Azure OpenAI.
- `CohereEmbeddings`: dung Cohere.
- `GeminiEmbeddings`: dung Google Gemini.
- `JinaEmbeddings`: dung Jina AI.
- `VoyageAIEmbeddings`: dung VoyageAI.
- Custom embeddings handler.

Voi RAG tieng Viet, embedding model la mot diem can test nghiem tuc. Recursive chunking tot nhung embedding kem van retrieval kem.

## 16. Refinery

### 16.1. Overlap Refinery

Overlap refinery them ngu canh tu chunk lien ke. Trong RAG, overlap giup chunk doc lap hon khi retrieval.

Trong Pipeline:

```python
.refine_with("overlap", context_size=100, method="prefix")
```

Hoac dung truc tiep:

```python
from chonkie.refinery import OverlapRefinery

overlap_refinery = OverlapRefinery(overlap_size=50)
chunks = overlap_refinery.refine(chunks)
```

Can can bang:

- Overlap qua nho: retrieval co the thieu ngu canh.
- Overlap qua lon: duplicate nhieu, ton storage/context, retrieval de trung lap.

### 16.2. Embeddings Refinery

Embeddings refinery gan embedding vao chunks:

```python
from chonkie.refinery import EmbeddingsRefinery

embeddings_refinery = EmbeddingsRefinery(
    embedding_model="minishlab/potion-base-32M"
)

chunks = embeddings_refinery.refine(chunks)
```

Huu ich neu muon chunk object da co `embedding` truoc khi dua vao vector DB.

## 17. Pipeline API va CHOMP

Chonkie Pipeline API dung fluent interface de ghep cac buoc xu ly.

Kien truc CHOMP:

```text
Fetcher -> Chef -> Chunker -> Refinery -> Porter/Handshake
```

### 17.1. Xu ly mot file

```python
from chonkie import Pipeline

doc = (
    Pipeline()
    .fetch_from("file", path="document.txt")
    .process_with("text")
    .chunk_with("recursive", chunk_size=512)
    .run()
)

print(len(doc.chunks))
```

### 17.2. Xu ly thu muc

```python
docs = (
    Pipeline()
    .fetch_from("file", dir="./documents", ext=[".md", ".txt"])
    .process_with("text")
    .chunk_with("recursive", chunk_size=512)
    .run()
)
```

Khuyen nghi luon filter extension de tranh doc binary/file rac.

### 17.3. Text input truc tiep

```python
doc = (
    Pipeline()
    .process_with("text")
    .chunk_with("semantic", threshold=0.8)
    .run(texts="Noi dung can chunk")
)
```

Nhieu texts:

```python
docs = (
    Pipeline()
    .chunk_with("recursive", chunk_size=512)
    .run(texts=["Text 1", "Text 2", "Text 3"])
)
```

### 17.4. Async

```python
pipe = Pipeline().chunk_with("recursive")
doc = await pipe.arun(texts="Async processing")
docs = await pipe.arun(texts=["Doc 1", "Doc 2"])
```

### 17.5. RAG pipeline mau

```python
from chonkie import Pipeline

docs = (
    Pipeline()
    .fetch_from("file", dir="./knowledge_base", ext=[".txt", ".md"])
    .process_with("text")
    .chunk_with("semantic", threshold=0.8, chunk_size=1024)
    .refine_with("overlap", context_size=100)
    .store_in(
        "qdrant",
        collection_name="knowledge",
        url="http://localhost:6333",
    )
    .run()
)
```

### 17.6. Export JSON

```python
docs = (
    Pipeline()
    .fetch_from("file", dir="./src", ext=[".py"])
    .chunk_with("code", chunk_size=512)
    .export_with("json", file="code_chunks.json")
    .run()
)
```

## 18. Pipeline validation

Theo docs, pipeline co validate:

- Bat buoc co it nhat mot chunker.
- Bat buoc co fetcher hoac input text qua `run(texts=...)`.
- Khong duoc co nhieu chef trong cung pipeline.

Hop le:

```python
Pipeline().fetch_from("file", path="doc.txt").chunk_with("recursive").run()
Pipeline().chunk_with("recursive").run(texts="Hello world")
```

Khong hop le:

```python
Pipeline().fetch_from("file", path="doc.txt").run()

Pipeline()
    .process_with("text")
    .process_with("markdown")
    .chunk_with("recursive")
```

## 19. Best practices tu docs

1. Luon set `chunk_size` ro rang

   Khong nen dua vao default vi default co the thay doi va kho reproduce.

2. Chon chunker theo loai noi dung

   - Code: `CodeChunker`
   - Bang: `TableChunker`
   - Van ban co cau truc: `RecursiveChunker`
   - Van ban can topic coherence: `SemanticChunker`
   - Can kich thuoc deu: `TokenChunker`

3. Dung refinery cho RAG

   Overlap context thuong giup retrieval tot hon.

4. Filter extension khi xu ly thu muc

   Tranh doc binary, cache, build artifacts, file tam.

5. Chain refineries khi can

   Vi du overlap truoc, embeddings sau:

   ```python
   .chunk_with("recursive", chunk_size=512)
   .refine_with("overlap", context_size=50)
   .refine_with("embedding", model="text-embedding-3-small")
   ```

## 20. De xuat ap dung vao project hien tai

Project hien co cac file lien quan:

- `apps/agent-service/app/indexing/llm_chunker.py`
- `apps/agent-service/app/indexing/chunk_slicer.py`
- `apps/agent-service/app/indexing/heading_parser.py`
- `apps/agent-service/app/core/llm.py`
- Tai lieu mau: `lichsu.clean.md`

Do corpus co ve la tai lieu tieng Viet/Markdown, huong an toan nhat:

1. Parse heading truoc

   Dung `heading_parser.py` de tach tai lieu thanh section logic. Metadata nen giu:

   - heading path
   - level
   - source file
   - ordinal/index
   - start/end line neu co

2. Chunk trong tung section bang `RecursiveChunker`

   Cau hinh hien tai chi tach theo paragraph va line:

   ```python
   rules = RecursiveRules(
       levels=[
           RecursiveLevel(delimiters=["\n\n"]),
           RecursiveLevel(delimiters=["\n"]),
       ]
   )
   ```

   Day la lua chon hop ly neu khong muon Chonkie cat nho xuong cau/tu. No giu paragraph tot hon va tranh pha cau truc Markdown.

3. Dung token counter rieng cho tieng Viet

   Wrapper hien tai:

   ```python
   def _chonkie_token_counter(text: str) -> int:
       return count_tokens(text)
   ```

   Diem hay la `count_tokens` duoc tra cuu luc goi, nen test co the monkeypatch duoc ngay ca khi chunker bi cache bang `lru_cache`.

4. Them overlap o tang project neu can

   Neu Chonkie rules da chunk theo section/paragraph, overlap co the xu ly sau bang logic rieng hoac `OverlapRefinery`.

   Khuyen nghi test:

   - no overlap
   - overlap 50 tokens
   - overlap 100 tokens

5. Chua nen voi dung SemanticChunker lam mac dinh

   SemanticChunker hap dan, nhung voi tieng Viet phu thuoc embedding model. Nen dung lam experiment so sanh voi RecursiveChunker:

   - Precision@k
   - Recall@k
   - MRR
   - ti le chunk bi dut y
   - ti le duplicate

6. Neu tai lieu Markdown co bang/code

   Can xem `MarkdownChef`, `TableChunker`, `CodeChunker` neu corpus co nhieu bang/code block. Neu khong, RecursiveChunker theo paragraph/line la don gian va de kiem soat hon.

## 21. Cau hinh khuyen nghi ban dau

Cho tai lieu tieng Viet dang Markdown:

```python
RecursiveChunker(
    tokenizer=_chonkie_token_counter,
    chunk_size=512,
    rules=RecursiveRules(
        levels=[
            RecursiveLevel(delimiters=["\n\n"]),
            RecursiveLevel(delimiters=["\n"]),
        ]
    ),
    min_characters_per_chunk=80,
)
```

Neu section dai va paragraph qua dai, co the them level cau:

```python
RecursiveRules(
    levels=[
        RecursiveLevel(delimiters=["\n\n"]),
        RecursiveLevel(delimiters=["\n"]),
        RecursiveLevel(delimiters=[". ", "! ", "? "], include_delim="prev"),
    ]
)
```

Nhung voi tieng Viet, them delimiter cau can test can than vi:

- So thu tu `1.`, `2.`, `3.` co the bi tach sai.
- Viet tat co dau cham co the bi tach sai.
- Markdown list co the bi anh huong.

## 22. Checklist test khi doi chunker

Khi thay doi chunking, nen co snapshot/metrics:

1. So chunk trung binh moi tai lieu.
2. Token trung binh/min/max moi chunk.
3. Ti le chunk vuot `max_tokens`.
4. Ti le chunk qua ngan.
5. Chunk co giu heading metadata khong.
6. Chunk co cat ngang paragraph/cau khong.
7. Retrieval test voi cau hoi tieng Viet that.
8. So sanh Recursive vs Semantic neu co embedding tot.
9. Thoi gian ingest.
10. Dung luong index/vector store.

## 23. Ket luan thuc dung

Voi project hien tai, Chonkie nen duoc xem la cong cu chunking co kha nang thay the/ho tro logic chia chunk thu cong. Lua chon nen uu tien:

- Mac dinh: `RecursiveChunker` theo section -> paragraph -> line.
- Bo sung: overlap sau chunking de cai thien retrieval.
- Thu nghiem: `SemanticChunker` voi embedding tieng Viet/multilingual.
- Rieng code/bang: dung `CodeChunker`/`TableChunker` neu corpus co nhieu noi dung dang do.

Cau hinh trong `llm_chunker.py` hien tai di dung huong: dung RecursiveChunker voi custom token counter tieng Viet, cache chunker theo tham so, va chi gom toi paragraph/line de giu cau truc tai lieu.
