export type ExampleTask = {
  id: string;
  label: string;
  task: string;
};

export const EXAMPLE_TASKS: ExampleTask[] = [
  {
    id: 'wiki-search',
    label: 'Search Wikipedia',
    task:
      'Go to wikipedia.org, search for "artificial intelligence", and extract the first paragraph of the article.',
  },
  {
    id: 'hn-story',
    label: 'Read Hacker News',
    task:
      'Go to news.ycombinator.com, click on the top story on the front page, then extract the title, the URL it links to, and the top 3 comments.',
  },
  {
    id: 'github-trending',
    label: 'Check GitHub trending',
    task:
      'Go to github.com/trending, find the #1 trending repository, and report its name, star count, and description.',
  },
  {
    id: 'recipe-lookup',
    label: 'Look up a recipe',
    task:
      'Go to allrecipes.com, search for "chocolate chip cookies", open the first result, and list the ingredients and total prep time.',
  },
  {
    id: 'product-search',
    label: 'Search for a product',
    task:
      'Go to amazon.com, search for "wireless mouse", sort by price low to high, and report the name, price, and rating of the first result.',
  },
];

/** Tasks from Browser Use's official BU_Bench_V1 benchmark. */
export const BENCHMARK_TASKS: ExampleTask[] = [
  {
    id: 'bu-stackexchange',
    label: 'BU Bench: StackExchange communities',
    task:
      'Browse the list of active Q&A communities on https://stackexchange.com and list the names of the top 5 communities by current activity.',
  },
  {
    id: 'bu-tmdb',
    label: 'BU Bench: TMDB movie search',
    task:
      'Use the advanced search to filter movies released in 2022 and output the first 5 results with their average ratings.\nwebsite: https://themoviedb.org',
  },
  {
    id: 'bu-newegg',
    label: 'BU Bench: Newegg product review',
    task:
      'Search for "NVIDIA RTX 3080" on Newegg, then review the "Review Bytes" summary for this product and output the three key performance highlights.\nwebsite: https://newegg.com',
  },
  {
    id: 'bu-metacritic',
    label: 'BU Bench: Metacritic TV shows',
    task:
      'Browse the TV shows category and list the titles, metascores, and number of critic reviews for shows scoring below 60 with at least 10 critic reviews.\nwebsite: https://metacritic.com',
  },
  {
    id: 'bu-bbcgoodfood',
    label: 'BU Bench: BBC Good Food recipe',
    task:
      'Open the "Keto Pancakes" recipe page and compile a list of the suggested ingredient substitutions provided.\nwebsite: https://www.bbcgoodfood.com/',
  },
];
