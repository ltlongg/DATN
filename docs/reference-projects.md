# Reference Projects For Custom RAG/GraphRAG

## Muc tieu tham khao

Project hien tai muon tu kiem soat luong code thay vi phu thuoc LightRAG:

```text
lichsu.md
  -> Chonkie chunking
  -> custom embedding model
  -> Qdrant vector storage
  -> graph extraction/storage
  -> hybrid retrieval
  -> rerank
  -> citation-grounded answer
```

Hai repo tham khao:

- https://github.com/phamtho034ls/RAGCHATBOTV2
- https://github.com/MacPhuPhong/TRAFFIC_LAW_LLM_RAG_AGENTIC

## 1. RAGCHATBOTV2

### Phan nen tham khao

- **Backend structure**: cach tach FastAPI service, ingestion, retrieval, rerank, config.
- **Qdrant usage**: cach tao collection, upsert vectors, luu payload, search top-k.
- **PostgreSQL metadata/search**: cach luu metadata rieng va ket hop voi vector search.
- **Hybrid retrieval**: ket hop vector search voi keyword/full-text search.
- **RRF / score fusion**: cach gop ket qua tu nhieu retriever.
- **Reranker layer**: dung reranker sau khi lay ung vien tu Qdrant.
- **Vietnamese embedding**: tham khao viec dung embedding model tieng Viet.
- **Ingestion pipeline**: cach parse tai lieu, chunk, embed, store.

### Phan co the hoc theo

```text
ingest document
  -> parse/clean
  -> chunk
  -> embed
  -> upsert Qdrant
  -> save metadata

query
  -> vector search
  -> keyword search
  -> fusion
  -> rerank
  -> build prompt context
  -> answer with citation
```

### Phan khong nen copy nguyen

- Chunking cua repo do gan voi domain phap luat; project nay nen thay bang Chonkie + markdown heading metadata.
- Metadata schema nen thiet ke lai cho lich su: `period`, `title`, `section`, `subsection`, `start_index`, `end_index`.
- Neu repo dung model/reranker cu the, chi lay y tuong layer, khong mac dinh dung y chang.

## 2. TRAFFIC_LAW_LLM_RAG_AGENTIC

### Phan nen tham khao

- **Agentic RAG flow**: router, retrieve, grade, generate, fallback.
- **LangGraph orchestration**: cach bieu dien luong truy van bang graph neu can agent workflow.
- **Hybrid search**: ket hop dense retrieval voi BM25/keyword.
- **Citation grounding**: cach gan cau tra loi voi nguon tai lieu.
- **Query grading**: danh gia context co du tra loi khong.
- **Web/HITL fallback**: chi tham khao neu sau nay can, chua nen lam ngay.

### Phan co the hoc theo

```text
query
  -> classify intent
  -> retrieve chunks
  -> grade relevance
  -> rerank/filter
  -> generate answer
  -> attach citations
```

### Phan khong nen copy nguyen

- Domain traffic law khac lich su, nen prompt extraction/retrieval phai viet lai.
- Neu workflow agent qua phuc tap, chi lay pattern sau khi baseline RAG da chay tot.
- Chua can HITL/web fallback trong phase dau neu dataset local la nguon chinh.

## Schema goi y cho Qdrant payload

Dung cho collection `chunks`:

```python
payload = {
    "text": chunk.text,
    "source": "lichsu.md",
    "chunk_index": i,
    "start_index": chunk.start_index,
    "end_index": chunk.end_index,
    "period": h1,
    "title": h2,
    "section": h3,
    "subsection": h4,
}
```

Trong do:

- `text`: noi dung chunk dua vao prompt.
- `source`: file nguon.
- `chunk_index`: thu tu chunk trong file.
- `start_index`, `end_index`: vi tri trong file goc de debug/citation.
- `period`: heading `#`, vi du `Thoi ki thuoc dia`.
- `title`: heading `##`, vi du `Khoi nghia Yen The`.
- `section`: heading `###`, vi du `Dien bien`.
- `subsection`: heading `####`, neu co.

## Chunking goi y bang Chonkie

```python
from chonkie import RecursiveChunker
from chonkie.types import RecursiveRules, RecursiveLevel

rules = RecursiveRules(levels=[
    RecursiveLevel(
        delimiters=["\n###### ", "\n##### ", "\n#### ", "\n### ", "\n## ", "\n# "],
        include_delim="next",
    ),
    RecursiveLevel(delimiters=["\n\n"], include_delim="next"),
    RecursiveLevel(delimiters=["\n"], include_delim="prev"),
    RecursiveLevel(delimiters=[". ", "! ", "? "], include_delim="prev"),
    RecursiveLevel(whitespace=True),
])

chunker = RecursiveChunker(
    tokenizer="character",
    chunk_size=1200,
    min_characters_per_chunk=80,
    rules=rules,
)
```

Sau khi baseline on dinh, co the doi sang:

```python
chunker = RecursiveChunker(
    tokenizer="tiktoken:gpt-4",
    chunk_size=700,
    min_characters_per_chunk=80,
    rules=rules,
)
```

## Roadmap nen lam

### Phase 1: Baseline RAG

- Chonkie chunking.
- Heading metadata.
- Custom embedding.
- Qdrant `chunks` collection.
- Dense retrieval top-k.
- Answer with citation.

### Phase 2: Hybrid Retrieval

- Them BM25/keyword search.
- Gop ket qua bang RRF hoac score fusion.
- Them reranker multilingual.

### Phase 3: Graph Layer

- Extract entities va relations tu chunk.
- Luu graph bang Neo4j hoac database rieng.
- Truy van ket hop vector chunks + graph facts.

### Phase 4: Agentic Flow

- Query routing.
- Relevance grading.
- Retry/refine query.
- Citation verification.

## Ket luan

- Lay **RAGCHATBOTV2** lam tham khao chinh cho storage, hybrid retrieval, rerank.
- Lay **TRAFFIC_LAW_LLM_RAG_AGENTIC** lam tham khao cho agent flow va citation grounding.
- Khong phu thuoc LightRAG trong phase dau; tu build pipeline de kiem soat chunking, embedding, Qdrant payload va graph logic.
