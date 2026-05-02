import os
from flask import Flask, jsonify, request
from psycopg_pool import ConnectionPool

app = Flask(__name__)

def get_db_url():
    return (
        f"host={os.environ.get('DB_HOST')} "
        f"dbname={os.environ.get('DB_DATABASE')} "
        f"user={os.environ.get('DB_USER')} "
        f"password={os.environ.get('DB_PASSWORD')}"
    )

pool = ConnectionPool(get_db_url(), min_size=1, max_size=5)
pool.wait()

def init_db():
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS item (
                    item_id SERIAL PRIMARY KEY,
                    priority VARCHAR(256) NOT NULL,
                    task VARCHAR(256) NOT NULL
                );
            """)
            conn.commit()

init_db()

@app.route("/")
def home():
    return """
    <h1>Flask + PostgreSQL con Docker Compose</h1>
    <p>API funcionando.</p>
    <ul>
        <li><a href="/api/health">Health check</a></li>
        <li><a href="/items">Items</a></li>
    </ul>
    """

@app.route("/api/health")
def health():
    return jsonify({
        "status": "healthy",
        "version": os.environ.get("APP_VERSION", "2.0.0")
    })

@app.route("/items", methods=["GET"])
def list_items():
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT item_id, priority, task FROM item ORDER BY item_id")
            rows = cur.fetchall()

    return jsonify([
        {"id": row[0], "priority": row[1], "task": row[2]}
        for row in rows
    ])

@app.route("/items/<int:item_id>", methods=["GET"])
def get_item(item_id):
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT item_id, priority, task FROM item WHERE item_id = %s",
                (item_id,)
            )
            row = cur.fetchone()

    if row is None:
        return jsonify({"error": "item not found"}), 404

    return jsonify({"id": row[0], "priority": row[1], "task": row[2]})

@app.route("/items", methods=["POST"])
def create_item():
    body = request.get_json()

    if not body or "priority" not in body or "task" not in body:
        return jsonify({"error": "priority and task are required"}), 400

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO item (priority, task)
                VALUES (%s, %s)
                RETURNING item_id, priority, task
                """,
                (body["priority"], body["task"])
            )
            row = cur.fetchone()
            conn.commit()

    return jsonify({
        "id": row[0],
        "priority": row[1],
        "task": row[2]
    }), 201

@app.route("/items/<int:item_id>", methods=["PUT"])
def update_item(item_id):
    body = request.get_json()

    if not body or "priority" not in body or "task" not in body:
        return jsonify({"error": "priority and task are required"}), 400

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE item
                SET priority = %s, task = %s
                WHERE item_id = %s
                RETURNING item_id, priority, task
                """,
                (body["priority"], body["task"], item_id)
            )
            row = cur.fetchone()
            conn.commit()

    if row is None:
        return jsonify({"error": "item not found"}), 404

    return jsonify({
        "id": row[0],
        "priority": row[1],
        "task": row[2]
    })

@app.route("/items/<int:item_id>", methods=["DELETE"])
def delete_item(item_id):
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM item WHERE item_id = %s RETURNING item_id",
                (item_id,)
            )
            row = cur.fetchone()
            conn.commit()

    if row is None:
        return jsonify({"error": "item not found"}), 404

    return jsonify({"message": "item deleted"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
