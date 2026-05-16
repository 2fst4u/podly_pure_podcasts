const { execSync } = require("node:child_process");

const resolveRepositoryUrl = () => {
  if (process.env.GITHUB_REPOSITORY) {
    return `https://github.com/${process.env.GITHUB_REPOSITORY}.git`;
  }

  try {
    return execSync("git remote get-url origin", { stdio: "pipe" })
      .toString()
      .trim();
  } catch {
    return undefined;
  }
};

const branches = ["main"];
if (
  process.env.GITHUB_REF_NAME &&
  process.env.GITHUB_REF_NAME !== "main" &&
  !process.env.GITHUB_REF_NAME.startsWith("v")
) {
  branches.push({ name: process.env.GITHUB_REF_NAME, prerelease: "dev" });
}

module.exports = {
  branches,
  repositoryUrl: resolveRepositoryUrl(),
  tagFormat: "v${version}",
  plugins: [
    [
      "@semantic-release/commit-analyzer",
      {
        preset: "angular",
        releaseRules: [
          { type: "docs", release: "patch" },
          { type: "refactor", release: "patch" },
          { type: "style", release: "patch" },
          { type: "chore", release: "patch" },
          { type: "test", release: "patch" },
          { type: "build", release: "patch" },
          { type: "ci", release: "patch" },
        ],
      },
    ],
    "@semantic-release/release-notes-generator",
    ["@semantic-release/changelog", { changelogFile: "CHANGELOG.md" }],
    [
      "@semantic-release/git",
      {
        assets: ["CHANGELOG.md"],
        message:
          "chore(release): ${nextRelease.version} [skip ci]\n\n${nextRelease.notes}",
      },
    ],
    [
      "@semantic-release/github",
      {
        addLabels: false,
        successComment: false,
      },
    ],
  ],
};
