#!/usr/bin/env python
import logging
import os
from json import dumps
from textwrap import dedent
from typing import cast

import neo4j
from flask import Flask, Response, request
from neo4j import GraphDatabase, basic_auth
from typing_extensions import LiteralString

app = Flask(__name__, static_url_path="/static/")

url = os.getenv("NEO4J_URI", "bolt://124.220.2.168:7687")
username = os.getenv("NEO4J_USER", "neo4j")
password = os.getenv("NEO4J_PASSWORD", "copd1234")
neo4j_version = os.getenv("NEO4J_VERSION", "4")
database = os.getenv("NEO4J_DATABASE", "hod.db")

port = int(os.getenv("PORT", 8080))

driver = GraphDatabase.driver(url, auth=basic_auth(username, password))


def query(q: LiteralString) -> LiteralString:
    # this is a safe transform:
    # no way for cypher injection by trimming whitespace
    # hence, we can safely cast to LiteralString
    return cast(LiteralString, dedent(q).strip())


@app.route("/")
def get_index():
    return app.send_static_file("index.html")



def serialize_node(node):
    return {
        "id": node.element_id,
        "name": node["name"],
        # "labels": list(node.labels)[0],
        # "content": node['content']
    }





@app.route("/graph")
def get_graph():
    records, _, _ = driver.execute_query(
        query("""
            MATCH (n)-[r]->(m)
            RETURN n, r, m
            LIMIT $limit
        """),
        database_=database,
        routing_="r",
        limit=int(request.args.get("limit", 100))
    )
    nodes = []
    rels = []
    for record in records:
        start_node = serialize_node(record[0])
        end_node = serialize_node(record[2])
        rel = record[1]
        # 添加起始节点和结束节点
        if start_node not in nodes:
            nodes.append(start_node)
        if end_node not in nodes:
            nodes.append(end_node)
        # 添加关系
        rels.append({"source": nodes.index(start_node), "target": nodes.index(end_node), "type": rel.type})
    return Response(dumps({"nodes": nodes, "links": rels}),
                    mimetype="application/json")

from flask import jsonify
@app.route("/search")
def get_search():
    try:
        q = request.args["q"]
        records, _, _ = driver.execute_query(
            query(f"""
                MATCH (node)
                WHERE toLower(node.name) CONTAINS toLower('q')
                RETURN node
            """),
            database_=database,
            routing_="r",
        )
        search_results = [serialize_node(record["node"]) for record in records]
        # 返回JSON响应
        return jsonify(search_results)


    except KeyError:
        return []



@app.route("/node/<node_type>/<name>")
def get_node_info(node_type, name):
    result = driver.execute_query(
        query(f"""
            MATCH (node:{node_type} {{name:$name}})
            OPTIONAL MATCH (node)-[r]-(related)
            RETURN node, COLLECT({{related: related, rel: r}}) AS related_info
            LIMIT 1
        """),
        name=name,
        database_=database,
        routing_="r",
        result_transformer_=neo4j.Result.single,
    )
    if not result:
        return Response(dumps({"error": f"{node_type.capitalize()} not found"}), status=404,
                        mimetype="application/json")

    node_info = serialize_node(result["node"])
    related_info = []
    for item in result["related_info"]:
        related_info.append({
            "related": serialize_node(item["related"]),
            "relation": item["rel"]["type"]
        })

    return Response(dumps({"node_info": node_info, "related_info": related_info}),
                    mimetype="application/json")



# @app.route("/node/<node_type>/<name>/vote", methods=["POST"])
# def vote_in_node(node_type, name):
#     summary = driver.execute_query(
#         query(f"""
#             MATCH (node:{node_type} {{name: $name}})
#             SET node.votes = coalesce(node.votes, 0) + 1;
#         """),
#         database_=database,
#         name=name,
#         result_transformer_=neo4j.Result.consume,
#     )
#     updates = summary.counters.properties_set
#     return Response(dumps({"updates": updates}), mimetype="application/json")

# from flask import request

@app.route("/add_node", methods=["POST"])
def add_node():
    data = request.get_json()
    node_type = data.get("node_type")
    properties = data.get("properties")
    
    # 在数据库中添加节点
    # 使用Neo4j的驱动执行相应的Cypher查询来添加节点
    
    return Response(dumps({"message": "Node added successfully"}), mimetype="application/json")

@app.route("/add_relationship", methods=["POST"])
def add_relationship():
    data = request.get_json()
    start_node_id = data.get("start_node_id")
    end_node_id = data.get("end_node_id")
    relationship_type = data.get("relationship_type")
    
    # 在数据库中添加关系
    # 使用Neo4j的驱动执行相应的Cypher查询来添加关系
    
    return Response(dumps({"message": "Relationship added successfully"}), mimetype="application/json")

@app.route("/update_node_properties", methods=["POST"])
def update_node_properties():
    data = request.get_json()
    node_id = data.get("node_id")
    updated_properties = data.get("updated_properties")
    
    # 在数据库中更新节点属性
    # 使用Neo4j的驱动执行相应的Cypher查询来更新节点属性
    
    return Response(dumps({"message": "Node properties updated successfully"}), mimetype="application/json")





if __name__ == "__main__":
    logging.root.setLevel(logging.INFO)
    logging.info("Starting on port %d, database is at %s", port, url)
    try:
        app.run(port=port)
    finally:
        driver.close()
