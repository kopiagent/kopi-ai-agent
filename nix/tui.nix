# nix/tui.nix — Kopi TUI (Ink/React) compiled with tsc and bundled
{ pkgs, kopiNpmLib, ... }:
let
  npm = kopiNpmLib.mkNpmPassthru {
    dirs = [
      "ui-tui"
      "apps/shared"
    ];
  };

  packageJson = builtins.fromJSON (builtins.readFile (npm.src + "/ui-tui/package.json"));
  version = packageJson.version;
in
pkgs.buildNpmPackage (npm // {
  pname = "kopi-tui";
  inherit version;

  doCheck = false;

  buildPhase = ''
    # esbuild bundles everything — no need for tsc or vite.
    # Run from the workspace root where node_modules/ lives.
    node ui-tui/scripts/build.mjs
  '';

  installPhase = ''
    runHook preInstall

    mkdir -p $out/lib/kopi-tui
    # esbuild writes to ui-tui/dist/ from the source root (no cd).
    cp -r ui-tui/dist $out/lib/kopi-tui/dist

    # package.json kept for "type": "module" resolution on `node dist/entry.js`.
    cp ui-tui/package.json $out/lib/kopi-tui/

    runHook postInstall
  '';
})
