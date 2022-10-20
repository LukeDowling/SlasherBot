CREATE TABLE IF NOT EXISTS tournament (
	MessageID integer,
	RoundNumber integer,
	MatchNumber integer,
	RedTeam integer,
	BlueTeam integer,
	Winner integer,
	PRIMARY KEY (MessageID, RoundNumber, MatchNumber)
);

CREATE TABLE IF NOT EXISTS draftPlayers (
	MessageID integer,
	PlayerID integer,
	Team integer,
	Captain boolean DEFAULT 0,
	DraftOrder integer,
	PRIMARY KEY (MessageID, PlayerID)
);

CREATE TABLE IF NOT EXISTS draftMessage (
	MessageID integer PRIMARY KEY,
	ChannelID integer,
	TeamSize integer
); 

CREATE TABLE IF NOT EXISTS guilds (
	GuildID integer PRIMARY KEY,
	Prefix text DEFAULT ">"
);

CREATE TABLE IF NOT EXISTS exp (
	UserID integer PRIMARY KEY,
	XP integer DEFAULT 0,
	Level integer DEFAULT 0,
	XPLock text DEFAULT CURRENT_TIMESTAMP
);
