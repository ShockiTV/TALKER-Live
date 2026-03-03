# audio-dll-ci-build

## Purpose

Defines the GitHub Actions CI workflow that builds `talker_audio.dll` from C source using MSVC and vcpkg, producing a pre-built x64 Windows binary committed to the repository.

## ADDED Requirements

### Requirement: GitHub Actions build workflow
A GitHub Actions workflow SHALL build `talker_audio.dll` on `windows-latest` using the MSVC toolchain pre-installed on the runner.

#### Scenario: Workflow triggers on native source changes
- **WHEN** a push or pull request modifies files under `native/` or the workflow file itself
- **THEN** the build workflow runs

#### Scenario: Successful build produces artifact
- **WHEN** the workflow runs on `windows-latest`
- **THEN** it produces `talker_audio.dll` as a build artifact
- **AND** the artifact is downloadable from the workflow run

### Requirement: vcpkg dependency management
The workflow SHALL use vcpkg to install PortAudio and Opus as static libraries. A `vcpkg.json` manifest in the `native/` directory SHALL declare these dependencies.

#### Scenario: vcpkg installs dependencies
- **WHEN** the build step runs
- **THEN** vcpkg installs `portaudio` and `opus` for the `x64-windows-static` triplet

#### Scenario: vcpkg.json declares dependencies
- **WHEN** the `native/vcpkg.json` file is read
- **THEN** it lists `portaudio` and `opus` as dependencies

### Requirement: CMake build configuration
The native source SHALL use CMake as the build system. CMakeLists.txt SHALL produce a shared library (DLL) with PortAudio and Opus statically linked.

#### Scenario: CMake generates MSVC project
- **WHEN** `cmake -B build -S native/ -DCMAKE_TOOLCHAIN_FILE=<vcpkg>` is run
- **THEN** CMake configures a build targeting x64 with MSVC

#### Scenario: Static linkage of dependencies
- **WHEN** the DLL is built
- **THEN** PortAudio and Opus are statically linked (no separate DLLs for them)
- **AND** the CRT is statically linked (`/MT`)

### Requirement: Binary committed to repository
The built `talker_audio.dll` SHALL be committed to `bin/pollnet/` alongside `pollnet.dll` so that mod users get the binary without building from source.

#### Scenario: DLL location in repository
- **WHEN** a user installs the mod
- **THEN** `bin/pollnet/talker_audio.dll` exists alongside `bin/pollnet/pollnet.dll`

#### Scenario: Binary updated on workflow success
- **WHEN** the CI build succeeds on the main branch
- **THEN** the updated `talker_audio.dll` binary is available for committing to the repo

### Requirement: x64 target architecture
The DLL SHALL be built as a 64-bit binary to match the game's x64 LuaJIT and `pollnet.dll`.

#### Scenario: Architecture matches game
- **WHEN** the DLL is loaded via `ffi.load()` in the game's 64-bit LuaJIT
- **THEN** it loads successfully without architecture mismatch errors

### Requirement: Exported C API symbols
The build SHALL export all 16 `ta_*` functions with C linkage (`extern "C"` / `__declspec(dllexport)`). No C++ name mangling SHALL be present in the export table.

#### Scenario: All symbols exported
- **WHEN** `dumpbin /exports talker_audio.dll` is run
- **THEN** all 16 `ta_*` function names appear unmangled

### Requirement: Native source directory structure
All C source, headers, CMakeLists.txt, and vcpkg.json SHALL reside under a `native/` top-level directory.

#### Scenario: Source layout
- **WHEN** a developer looks at the `native/` directory
- **THEN** it contains at minimum: `CMakeLists.txt`, `vcpkg.json`, `talker_audio.c` (or `.h`/`.c` split)
