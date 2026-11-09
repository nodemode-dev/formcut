export const SRT = `1
00:00:03,920 --> 00:00:08,120
I went to the woods because I wished to live deliberately,

2
00:00:09,200 --> 00:00:12,170
to front only the essential facts of life,

3
00:00:13,070 --> 00:00:15,890
and see if I could not learn what it had to teach,

4
00:00:16,820 --> 00:00:20,390
and not, when I came to die, discover that I had not lived.

5
00:00:22,340 --> 00:00:28,130
I did not wish to live what was not life, living is so dear;

6
00:00:28,820 --> 00:00:33,290
nor did I wish to practise resignation, unless it was quite necessary.

7
00:00:34,580 --> 00:00:40,370
I wanted to live deep and suck out all the marrow of life,

8
00:00:41,330 --> 00:00:48,530
to live so sturdily and Spartan-like as to put to rout all that was not life,

9
00:00:49,070 --> 00:00:52,340
to cut a broad swath and shave close,

10
00:00:52,910 --> 00:00:57,920
to drive life into a corner, and reduce it to its lowest terms,

11
00:00:57,980 --> 00:01:00,980
and, if it proved to be mean,

12
00:01:01,880 --> 00:01:05,390
why then to get the whole and genuine meanness of it,

13
00:01:05,930 --> 00:01:08,390
and publish its meanness to the world;

14
00:01:09,260 --> 00:01:15,230
or if it were sublime, to know it by experience,

15
00:01:15,530 --> 00:01:19,670
and be able to give a true account of it in my next excursion.
`;

export interface Chapter {
  t: number;
  title: string;
}

export const CHAPTERS: Chapter[] = [
  { t: 0, title: "To live deliberately" },
  { t: 34.6, title: "Live deep" },
  { t: 57.98, title: "Mean or sublime" },
  { t: 80.4, title: "Credits" },
];

export const FILM_LENGTH = 86;
export const VOICE_START = 3;
