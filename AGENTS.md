# Repository guidance

## Setup and verification
- Open `Detectsystemp.uproject` with Unreal Engine **5.6**. This is a Blueprint/content-only project: no `Source/`, C++ modules, or repository-defined build, lint, or automated-test commands.
- The project enables `Locomotor`, `GameplayStateTree`, `PhysicsControl`, and editor-only `ModelingToolsEditorMode`; ensure the engine installation provides these plugins, especially `Locomotor`, rather than disabling them to bypass startup errors.
- `Plugins/EngineWire/` contains EngineWire 0.6.0 with local Win64 binaries built for UE 5.6.1. Its native MCP server defaults to loopback port 3000; the capability token is generated in `Saved/MCP/capability-token` and must not be committed. Plugin binaries are ignored by Git, so a fresh checkout needs a matching prebuilt plugin or a separate `RunUAT.bat BuildPlugin` build (the project has no C++ target).
- Keep `MovieRenderPipeline` and `MoviePipelineMaskRenderPass` enabled in `.uproject`: this EngineWire build imports their DLLs directly and fails to load with Windows error 126 if they are disabled, despite its optional plugin declarations.
- For gameplay changes, compile the affected Blueprints in Unreal Editor and exercise them in Play In Editor on `/Game/ThirdPerson/Lvl_ThirdPerson`. Report editor verification as unperformed if Unreal is unavailable.

## Where behavior lives
- `Task.md` is the Beholder specification: checked `[УТВЕРЖДЕНО]` items are approved requirements, not implemented features. Actual progress is in section 16 and `docs/BeholderPrototype.md`. New isolated eye-prototype assets live in `Content/BeholderPrototype/`; do not mistake its masked eyelid and primitive claws for the final organic rig.
- `docs/BeholderLegPrototype.md` documents the isolated leg copies and PIE measurements. Keep their `EyeTip` socket force-animated (otherwise mesh Foot_end stayed at the origin); the imported Hip has scale 100. The spline prototype is not telescopic locomotion, and needs no AnimBP because ControlRigComponent maps the bones.
- The leg's `HeadModule` uses `BP_Lapa5_Head`, attached through SCS_Node.AttachToName=`EyeTip` with Roll −90°. Claws now orbit the **sphere center**, not their base edges; do not restore the old edge-pivot calibration. See `docs/Lapa5Head.md`. Parser tests: `python -m unittest discover -s tools -p "test_*.py"`; `tools/validate_lapa5_spherical.py` and calibration require Unreal editor Python, not standalone Python.
- `Config/DefaultEngine.ini` selects both the startup/game map (`/Game/ThirdPerson/Lvl_ThirdPerson`) and default game mode (`/Game/ThirdPerson/Blueprints/BP_ThirdPersonGameMode`). The template map path in `DefaultEditor.ini` is not the configured startup map.
- Custom search assets are in **`Content/Bluprient/`** (intentional existing spelling): `BPC_Search_SYS`, `BPC_Sercher_Stats`, `BP_Searcher`, `BP_SearchTower`, and `BP_ObjectToSearch`. Preserve these exact asset paths/names; do not normalize spelling from the filesystem.
- Beholder/rig experiments are under `Content/Bluprient/Beholder/` and `Content/Bluprient/New_Beh/`; the third-person character/controller/game mode are under `Content/ThirdPerson/Blueprints/`.
- Input uses **Enhanced Input** (`Config/DefaultInput.ini`); action and mapping-context assets live under `Content/Input/`, not legacy INI action mappings.

## Asset and configuration pitfalls
- `.uasset` and `.umap` files are binary source assets; edit through Unreal Editor, not text patches. Rename/move assets in the editor so references and redirectors are handled.
- The third-person level has companion assets under `Content/__ExternalActors__/` and `Content/__ExternalObjects__/`; include relevant companion changes with level edits. Assets under `Content/_GENERATED/` and `Content/ThirdPerson/_GENERATED/` are tracked content, not disposable build caches.
- Change shared project defaults in `Config/Default*.ini`, not generated `Saved/Config/WindowsEditor/` settings.
- `Saved/`, `Intermediate/`, and `DerivedDataCache/` contain already-tracked files despite `.gitignore`. Editor runs can dirty logs/settings; inspect `git status --short` and keep that churn out of task changes. Do not bulk-delete or untrack these directories as incidental cleanup.
