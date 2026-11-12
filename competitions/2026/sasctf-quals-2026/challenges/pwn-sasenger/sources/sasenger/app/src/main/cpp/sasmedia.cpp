// sasmedia.cpp — JNI surface for libsasmedia.so.
//
// One entry point: decode an inbound "SMC1" message container into an array of
// display-ready parts (text / image / sticker). Invoked 0-click on every inbound
// message (see core.Repository). The decode — and the vulnerability — live in
// message.cpp.
//
// SPDX-License-Identifier: Proprietary
#include <jni.h>

#include <cstdint>

#include "message.hpp"

namespace {

constexpr const char* kPartClass = "com/sasctf/sasenger/media/MessagePart";
// MessagePart(int kind, String text, int width, int height, int[] pixels,
//             int stickerId, int[] palette)
constexpr const char* kPartCtorSig = "(ILjava/lang/String;II[II[I)V";

// Kotlin-side kind constants (MessagePart.KIND_*).
constexpr jint kKindText = 0;
constexpr jint kKindImage = 1;
constexpr jint kKindSticker = 2;
constexpr jint kKindReply = 3;

jintArray to_int_array(JNIEnv* env, const std::vector<std::uint32_t>& v) {
    jintArray arr = env->NewIntArray(static_cast<jsize>(v.size()));
    if (arr != nullptr && !v.empty()) {
        env->SetIntArrayRegion(arr, 0, static_cast<jsize>(v.size()),
                               reinterpret_cast<const jint*>(v.data()));
    }
    return arr;
}

}  // namespace

extern "C" JNIEXPORT jobjectArray JNICALL
Java_com_sasctf_sasenger_media_MediaCodec_nativeCompose(JNIEnv* env, jclass,
                                                        jbyteArray payload) {
    if (payload == nullptr) return nullptr;

    const jsize len = env->GetArrayLength(payload);
    jbyte* buf = env->GetByteArrayElements(payload, nullptr);
    if (buf == nullptr) return nullptr;

    sasmedia::RenderedMessage msg;
    const bool ok = sasmedia::compose_message(
        reinterpret_cast<const std::uint8_t*>(buf), static_cast<std::size_t>(len), msg);
    // The decode owns no reference into `buf`; release without copy-back. (A probe
    // that dereferences a corrupted surface crashes inside compose_message and
    // never reaches here — that silence is the 1-bit oracle.)
    env->ReleaseByteArrayElements(payload, buf, JNI_ABORT);
    if (!ok) return nullptr;

    jclass cls = env->FindClass(kPartClass);
    if (cls == nullptr) return nullptr;
    jmethodID ctor = env->GetMethodID(cls, "<init>", kPartCtorSig);
    if (ctor == nullptr) return nullptr;

    jobjectArray result =
        env->NewObjectArray(static_cast<jsize>(msg.parts.size()), cls, nullptr);
    if (result == nullptr) return nullptr;

    jsize index = 0;
    for (const sasmedia::RenderedPart& part : msg.parts) {
        jint kind = kKindText;
        jstring text = nullptr;
        jint width = 0, height = 0, stickerId = -1;
        jintArray pixels = nullptr;
        jintArray palette = nullptr;

        switch (part.kind) {
        case sasmedia::PartKind::Text:
            kind = kKindText;
            text = env->NewStringUTF(part.text.c_str());
            break;
        case sasmedia::PartKind::Reply:
            kind = kKindReply;
            text = env->NewStringUTF(part.text.c_str());
            break;
        case sasmedia::PartKind::Image:
            kind = kKindImage;
            width = static_cast<jint>(part.width);
            height = static_cast<jint>(part.height);
            pixels = to_int_array(env, part.pixels);
            break;
        case sasmedia::PartKind::Sticker:
            kind = kKindSticker;
            stickerId = part.sticker_id;
            palette = to_int_array(env, part.palette);
            break;
        }

        jobject obj = env->NewObject(cls, ctor, kind, text, width, height,
                                     pixels, stickerId, palette);
        env->SetObjectArrayElement(result, index++, obj);

        // Keep the local-reference table bounded across many/large parts.
        if (text != nullptr) env->DeleteLocalRef(text);
        if (pixels != nullptr) env->DeleteLocalRef(pixels);
        if (palette != nullptr) env->DeleteLocalRef(palette);
        if (obj != nullptr) env->DeleteLocalRef(obj);
    }
    return result;
}
