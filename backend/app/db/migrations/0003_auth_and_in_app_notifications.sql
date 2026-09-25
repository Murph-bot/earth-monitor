-- Phase 8: real auth + in-app alert channel.
--
-- users.password_hash is nullable: pre-auth dev users have none and simply
-- can't log in — they only exist through the EM_DEV_USER_EMAIL seam.
ALTER TABLE users ADD COLUMN password_hash text;

-- in_app joins email/web_push/mobile_push: the in-app inbox is a channel,
-- not a separate system — senders read one table either way.
ALTER TABLE notifications DROP CONSTRAINT notifications_channel_check;
ALTER TABLE notifications ADD CONSTRAINT notifications_channel_check
    CHECK (channel IN ('email', 'web_push', 'mobile_push', 'in_app'));

-- scene_id dedup anchor: (alert_rule_id, scene_id) makes a re-analyzed scene
-- unable to double-notify. NULL = notifications not tied to a scene (system
-- messages, channel test pings).
ALTER TABLE notifications ADD COLUMN scene_id bigint REFERENCES scenes(id) ON DELETE SET NULL;
ALTER TABLE notifications ADD COLUMN read_at timestamptz;
ALTER TABLE notifications ADD CONSTRAINT notifications_rule_scene_uniq
    UNIQUE (alert_rule_id, scene_id);
CREATE INDEX notifications_user_unread_idx
    ON notifications (user_id) WHERE read_at IS NULL;
