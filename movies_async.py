#!/usr/bin/env python
import logging
import os
from contextlib import asynccontextmanager
from textwrap import dedent
from typing import Optional, cast

import neo4j
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from neo4j import AsyncGraphDatabase
from typing_extensions import LiteralString


PATH = os.path.dirname(os.path.abspath(__file__))

url = os.getenv("NEO4J_URI", "bolt://124.220.2.168:7687")
username = os.getenv("NEO4J_USER", "neo4j")
password = os.getenv("NEO4J_PASSWORD", "copd1234")
neo4j_version = os.getenv("NEO4J_VERSION", "4")
database = os.getenv("NEO4J_DATABASE", "hod.db")

port = int(os.getenv("PORT", 8080))

shared_context = {}


def query(q: LiteralString) -> LiteralString:
    # this is a safe transform:
    # no way for cypher injection by trimming whitespace
    # hence, we can safely cast to LiteralString
    return cast(LiteralString, dedent(q).strip())


@asynccontextmanager
async def lifespan(app: FastAPI):
    driver = AsyncGraphDatabase.driver(url, auth=(username, password))
    shared_context["driver"] = driver
    yield
    await driver.close()


def get_driver() -> neo4j.AsyncDriver:
    return shared_context["driver"]


app = FastAPI(lifespan=lifespan)


@app.get("/")
async def get_index():
    return FileResponse(os.path.join(PATH, "static", "index.html"))


def serialize_disease(node):
    return {
        "id": node.element_id,
        "name": node["name"],
        "labels": list(node.labels)[0],
        "content": node['content']
    }


@app.get("/graph")
async def get_graph(limit: int = 5):
    records, _, _ = await get_driver().execute_query(
        query("""
            MATCH (n)-[r]->(m)
            RETURN n, r, m
            LIMIT $limit
        """),
        database_=database,
        routing_="r",
        limit=limit,
    )
    nodes = []
    rels = []
    for record in records:
        start_node = serialize_disease(record[0])
        end_node = serialize_disease(record[2])
        rel = record[1]
        # 添加起始节点和结束节点
        if start_node not in nodes:
            nodes.append(start_node)
        if end_node not in nodes:
            nodes.append(end_node)
        # 添加关系
        rels.append({"source": nodes.index(start_node), "target": nodes.index(end_node), "type": rel.type})
    return {"nodes": nodes, "links": rels}


@app.get("/search")
async def get_search(q: Optional[str] = None):
    if q is None:
        return []
    records, _, _ = await get_driver().execute_query(
        query(f"""
                MATCH (node)
                WHERE toLower(node.name) CONTAINS toLower('{q}')
                RETURN node LIMIT 5
        """),
        database_=database,
        routing_="r",
    )
    return [serialize_disease(record["node"]) for record in records]


# @app.get("/movie/{title}")
# async def get_movie(title: str):
#     result = await get_driver().execute_query(
#         query("""
#             MATCH (movie:Movie {title:$title})
#             OPTIONAL MATCH (movie)<-[r]-(person:Person)
#             RETURN movie.title as title,
#             COLLECT(
#                 [person.name, HEAD(SPLIT(TOLOWER(TYPE(r)), '_')), r.roles]
#             ) AS cast
#             LIMIT 1
#         """),
#         title=title,
#         database_=database,
#         routing_="r",
#         result_transformer_=neo4j.AsyncResult.single,
#     )
#     if result is None:
#         raise HTTPException(status_code=404, detail="Movie not found")

#     return {"title": result["title"],
#             "cast": [serialize_cast(member)
#                      for member in result["cast"]]}


# @app.post("/movie/{title}/vote")
# async def vote_in_movie(title: str):
#     summary = await get_driver().execute_query(
#         query("""
#             MATCH (m:Movie {title: $title})
#             SET m.votes = coalesce(m.votes, 0) + 1;
#         """),
#         database_=database,
#         title=title,
#         result_transformer_=neo4j.AsyncResult.consume,
#     )
#     updates = summary.counters.properties_set

#     return {"updates": updates}


if __name__ == "__main__":
    import uvicorn

    logging.root.setLevel(logging.INFO)
    logging.info("Starting on port %d, database is at %s", port, url)

    uvicorn.run(app, port=port)
