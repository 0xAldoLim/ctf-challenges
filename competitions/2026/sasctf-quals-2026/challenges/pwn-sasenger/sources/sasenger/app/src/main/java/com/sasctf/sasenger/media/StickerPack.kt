package com.sasctf.sasenger.media

object StickerPack {
    class Sticker(val id: Int, val glyph: String, val palette: IntArray)

    val all: List<Sticker> = listOf(
        Sticker(0, "😎", intArrayOf(0xFF42A5F5.toInt(), 0xFF1E1E1E.toInt(), 0xFFFFD54F.toInt())),
        Sticker(1, "🔥", intArrayOf(0xFFFF7043.toInt(), 0xFFFFCA28.toInt(), 0xFFD84315.toInt())),
        Sticker(2, "❤️", intArrayOf(0xFFE53935.toInt(), 0xFFFF8A80.toInt())),
        Sticker(3, "👍", intArrayOf(0xFFFFB300.toInt(), 0xFFFFE082.toInt())),
        Sticker(4, "🎉", intArrayOf(0xFFAB47BC.toInt(), 0xFF26C6DA.toInt(), 0xFFFFEE58.toInt())),
        Sticker(5, "😂", intArrayOf(0xFFFFCA28.toInt(), 0xFFFFA726.toInt())),
    )

    fun byId(id: Int): Sticker? = all.getOrNull(id)

    fun palette(id: Int): IntArray = byId(id)?.palette ?: intArrayOf(0xFF888888.toInt())
}
