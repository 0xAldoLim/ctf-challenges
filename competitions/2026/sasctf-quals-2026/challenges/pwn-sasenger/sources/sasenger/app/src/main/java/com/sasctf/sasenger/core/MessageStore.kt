package com.sasctf.sasenger.core

import android.content.ContentValues
import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import com.sasctf.sasenger.media.MessagePart
import com.sasctf.sasenger.model.Message
import org.json.JSONArray
import org.json.JSONObject

class MessageStore(ctx: Context) : SQLiteOpenHelper(ctx, DB, null, VERSION) {

    override fun onCreate(db: SQLiteDatabase) {
        db.execSQL(
            "CREATE TABLE messages (" +
                "id TEXT PRIMARY KEY, peer TEXT, incoming INTEGER, parts TEXT, ts INTEGER, delivery TEXT)"
        )
        db.execSQL("CREATE TABLE secrets (k TEXT PRIMARY KEY, v TEXT)")
    }

    override fun onUpgrade(db: SQLiteDatabase, oldV: Int, newV: Int) {
        db.execSQL("DROP TABLE IF EXISTS messages")
        db.execSQL("DROP TABLE IF EXISTS secrets")
        onCreate(db)
    }

    fun insert(m: Message) {
        val v = ContentValues().apply {
            put("id", m.id)
            put("peer", m.peer)
            put("incoming", if (m.incoming) 1 else 0)
            put("parts", serialize(m.parts))
            put("ts", m.ts)
            put("delivery", m.deliveryState.value)
        }
        writableDatabase.insertWithOnConflict("messages", null, v, SQLiteDatabase.CONFLICT_IGNORE)
    }

    fun updateDelivery(id: String, state: String) {
        val v = ContentValues().apply { put("delivery", state) }
        writableDatabase.update("messages", v, "id = ?", arrayOf(id))
    }

    fun putSecret(key: String, value: String) {
        val v = ContentValues().apply { put("k", key); put("v", value) }
        writableDatabase.insertWithOnConflict("secrets", null, v, SQLiteDatabase.CONFLICT_REPLACE)
    }

    fun loadAll(): List<Message> {
        val out = ArrayList<Message>()
        readableDatabase.query("messages", null, null, null, null, null, "ts ASC").use { c ->
            val iId = c.getColumnIndexOrThrow("id")
            val iPeer = c.getColumnIndexOrThrow("peer")
            val iIn = c.getColumnIndexOrThrow("incoming")
            val iParts = c.getColumnIndexOrThrow("parts")
            val iTs = c.getColumnIndexOrThrow("ts")
            val iDel = c.getColumnIndexOrThrow("delivery")
            while (c.moveToNext()) {
                val m = Message(
                    id = c.getString(iId),
                    peer = c.getString(iPeer),
                    incoming = c.getInt(iIn) == 1,
                    parts = deserialize(c.getString(iParts) ?: "[]"),
                    ts = c.getLong(iTs),
                )
                m.deliveryState.value = if (c.isNull(iDel)) null else c.getString(iDel)
                out.add(m)
            }
        }
        return out
    }

    fun clear() {
        writableDatabase.delete("messages", null, null)
        writableDatabase.delete("secrets", null, null)
    }

    private fun serialize(parts: List<MessagePart>): String {
        val arr = JSONArray()
        for (p in parts) {
            val o = JSONObject().put("k", p.kind)
            when (p.kind) {
                MessagePart.KIND_TEXT, MessagePart.KIND_REPLY -> o.put("t", p.text ?: "")
                MessagePart.KIND_IMAGE -> o.put("w", p.width).put("h", p.height)
                MessagePart.KIND_STICKER -> {
                    o.put("s", p.stickerId)
                    p.palette?.let { pal -> o.put("p", JSONArray().apply { pal.forEach { put(it) } }) }
                }
            }
            arr.put(o)
        }
        return arr.toString()
    }

    private fun deserialize(s: String): List<MessagePart> {
        val arr = JSONArray(s)
        val out = ArrayList<MessagePart>(arr.length())
        for (i in 0 until arr.length()) {
            val o = arr.getJSONObject(i)
            when (val k = o.getInt("k")) {
                MessagePart.KIND_TEXT, MessagePart.KIND_REPLY ->
                    out.add(MessagePart(k, o.optString("t"), 0, 0, null, -1, null))
                MessagePart.KIND_IMAGE ->
                    out.add(MessagePart(k, null, o.optInt("w"), o.optInt("h"), null, -1, null))
                MessagePart.KIND_STICKER -> {
                    val pal = o.optJSONArray("p")?.let { a -> IntArray(a.length()) { a.getInt(it) } }
                    out.add(MessagePart(k, null, 0, 0, null, o.optInt("s", -1), pal))
                }
            }
        }
        return out
    }

    companion object {
        private const val DB = "sasenger.db"
        private const val VERSION = 4
    }
}
