cmake_minimum_required(VERSION 3.20)
project(talker_audio C)

# ── Find dependencies (installed by vcpkg) ──────────────────────────────────

find_package(portaudio CONFIG REQUIRED)
find_package(Opus CONFIG REQUIRED)

# ── Shared library (DLL) ────────────────────────────────────────────────────

add_library(talker_audio SHARED talker_audio.c)

target_link_libraries(talker_audio
    PRIVATE
        portaudio
        Opus::opus
)

# ── Static CRT on MSVC (/MT) ────────────────────────────────────────────────

if(MSVC)
    set_property(TARGET talker_audio PROPERTY
        MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>"
    )
    # Suppress warning about non-standard extension used (nameless struct)
    target_compile_options(talker_audio PRIVATE /W3)
endif()

# ── Export all ta_* symbols via .def or declspec ─────────────────────────────

target_compile_definitions(talker_audio PRIVATE TALKER_AUDIO_EXPORTS)

# ── Output name without lib prefix ──────────────────────────────────────────

set_target_properties(talker_audio PROPERTIES
    PREFIX ""
    OUTPUT_NAME "talker_audio"
)
