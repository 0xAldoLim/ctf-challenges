package com.sasctf.sasenger.media

object MediaCodec {
    init { System.loadLibrary("sasmedia") }

    @JvmStatic external fun nativeCompose(payload: ByteArray): Array<MessagePart>?
}
