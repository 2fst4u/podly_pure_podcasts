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

module.exports = {
  branches: ["main", { name: "*", prerelease: "dev" }],
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
