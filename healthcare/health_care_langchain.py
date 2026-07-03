from dotenv import load_dotenv
import os
from langchain_neo4j import Neo4jGraph

load_dotenv()

AURA_INSTANCENAME = os.environ["AURA_INSTANCENAME"]
AURA_INSTANCEID = os.environ["AURA_INSTANCEID"]
NEO4J_URI = os.environ["NEO4J_URI"]
NEO4J_USERNAME = os.environ["NEO4J_USERNAME"]
NEO4J_PASSWORD = os.environ["NEO4J_PASSWORD"]
NEO4J_DATABASE = os.environ["NEO4J_DATABASE"]
AUTH = (NEO4J_USERNAME, NEO4J_PASSWORD)

kg = Neo4jGraph(
    url=NEO4J_URI,
    username=NEO4J_USERNAME,
    password=NEO4J_PASSWORD,
    database=NEO4J_DATABASE,
)

cypher = """
MATCH (n)
RETURN count(n) as numberOfNodes
"""

result = kg.query(cypher)
print(f"There are {result[0]['numberOfNodes']} nodes in the graph database.")

# Match only the Providers nodes by specifying the node label
cypher = """
MATCH (n:HealthcareProvider)
RETURN count(n) as numberOfProviders
"""

res = kg.query(cypher)
print(
    f"There are {res[0]['numberOfProviders']} healthcare provider nodes in the graph database."
)

# return the names of the Healthcare Providers
cypher = """
MATCH (n:HealthcareProvider)
RETURN n.name as providerName
"""

res = kg.query(cypher)
print("Healthcare Providers in the graph database:")
for row in res:
    print(f" - {row['providerName']}")

# list all patients in the graph
cypher = """
MATCH (n:Patient)
RETURN n.name as patientName
LIMIT 10
"""
res = kg.query(cypher)
print("Patients in the graph database:")
for row in res:
    print(f" - {row['patientName']}")

# list all specializations in the graph
cypher = """
MATCH (n:Specialization)
RETURN n.name as specializationName
"""
res = kg.query(cypher)
print("Specializations in the graph database:")
for row in res:
    print(f" - {row['specializationName']}")

# list all locations in the graph
cypher = """
MATCH (n:Location)
RETURN n.name as locationName
"""
res = kg.query(cypher)
print("Locations in the graph database:")
for row in res:
    print(f" - {row['locationName']}")

# list all patients treated by a specific healthcare provider
cypher = """
MATCH (hp:HealthcareProvider {name: 'Dr. Smith'})-[:TREATS]->(p:Patient)
RETURN p.name as patientName
"""
res = kg.query(cypher)
print("Patients treated by Dr. Smith:")
for row in res:
    print(f" - {row['patientName']}")
