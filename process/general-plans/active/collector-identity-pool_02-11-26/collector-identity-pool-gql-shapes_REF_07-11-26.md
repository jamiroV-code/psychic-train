# GraphQL request/response shapes (S-RGQL Stage 0) — 07-11-26

Source: public Redlib fork `Nachtalb/redlib` `main` (read 07-11-26): `src/backends/gql.rs`, `src/oauth.rs`. These are SHAPES for the fake and the B7 templates. They are not evidence about the live service; PR1 decides that.

## Token mint (`oauth.rs`, MobileSpoofAuth)
- `POST https://www.reddit.com/auth/v2/oauth/access-token/loid`
- Headers: Android device headers (`User-Agent` Android app, `x-reddit-retry`, `x-reddit-compression`, `x-reddit-qos`, `x-reddit-media-codecs`, `Content-Type: application/json; charset=UTF-8`, `client-vendor-id`/`X-Reddit-Device-Id` = random UUID), plus `Authorization: Basic base64(<Android client id>:)`.
- Body `{"scopes": ["*","email","pii","adsread","adsedit"]}`. Response `{access_token, expires_in}`. The response headers `x-reddit-loid`/`x-reddit-session` are echoed back by Redlib; the source notes this is "technically not needed". We do not echo them (credential-named; B7 refuses them).
- Rate: "600 per token"; Redlib refreshes when `x-ratelimit-remaining` < 60.

## Operations (`gql.rs`)
- `POST https://gql-fed.reddit.com/` body `{operationName, variables, extensions:{persistedQuery:{version:1, sha256Hash}}}`; headers `X-APOLLO-OPERATION-NAME`, `X-APOLLO-OPERATION-ID`, Accept, the device headers, `Authorization: Bearer <token>`. Raw query text is rejected (persisted hashes only).
- Subreddit feed `SubredditFeedElements`: variables `{subredditName, sort:"NEW", pageSize, includeSubredditInPosts:true, after: base64(<previous last t3 id>)}`. Response `data.postFeed.elements{edges[].node, pageInfo{hasNextPage, endCursor}}`. Nodes: `__typename` (`SubredditPost`; ads and recommendation units are other types), `id` (t3), `title`, `createdAt` (ISO with offset), `authorInfo.name`, `subreddit.name`, `commentCount`, `content.markdown`.
- `PostComments`: variables `{id:"t3_…", sortType, count:200, maxDepth:10, includeConsistencyToken:false, after?}`. Response `data.postInfoById.commentForest.trees[]{depth, parentId, node{__typename: Comment|DeletedComment, id t1, authorInfo, content.markdown, createdAt}, more{cursor,count}}`. At most 200 comments per request, depth 10, "more" cursors.
- Partial data: fields can come back null with `errors` beside `data`; Redlib retries once.

## Fixture assumptions to confirm by PR1 (B2: misfit = `schema_mismatch`)
- The comment node's subreddit name: the grammar needs one per item; the fake puts `subredditName` on the comment node. The real `PostComments` tree may hold it only on `postInfoById.subreddit`. If so, PR1 fails `schema_mismatch` and the owner's "extend parser" decision applies.
- The comment-forest page cursor: the fake uses `commentForest.pageInfo`; the real tree carries `more.cursor` per entry.
- Full-text proof: the fake uses `selftext_full`; PR1 must show that `content.markdown` is the complete body.
- A rejected persisted hash: the fake answers `errors[].message = "PersistedQueryNotFound"` (Apollo convention). This is not observed on Reddit.
