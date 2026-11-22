# Changelog

## Unreleased

### Added

- Group hierarchy support: `parent_group_id` on list, create, and update group
  operations. Updates omitting `parent_group_id` preserve the current parent;
  an explicit null parent moves the group to the root level.

### Changed

- Replaced `add_knowledge_text` with unified `add_knowledge_file` supporting
  text uploads, base64 binary uploads, and attaching existing Open WebUI files
  by `file_id`.

### Fixed

- Uploads that include `knowledge_id` now pass `metadata.knowledge_id` on file
  creation so Open WebUI links synchronously instead of racing a second attach
  call.

## 0.2.0 - 2026-09-05

### Added

- Added access sharing for knowledge bases through the MCP management tool.
- Added file upload support with optional knowledge-base linking.
- Added discovery of effective provider, base, and custom models.

### Fixed

- Followed pagination for users, files, and knowledge bases.
- Avoided downloading extracted file content during file listings.
- Corrected system configuration lookup to use Open WebUI's export endpoint.
- Aligned management routes with current Open WebUI APIs.
- Encoded query parameters and resource IDs safely.
- Forwarded authenticated Open WebUI session tokens correctly for scoped profiles.

