# book_reader.py
# This function reads a text file and splits it into pages and allows the player to read books

import pygame
import os

from config import WIDTH, HEIGHT

# To use in teh game:
# from book_reader import BookReader

# def open_book():
#     reader = BookReader("data/moby_dick.txt")
#     reader.run()
# book_reader.py

def wrap_line(text, font, max_width):
    words = text.split()
    lines = []
    current_line = ""
    for word in words:
        test_line = current_line + " " + word if current_line else word
        if font.size(test_line)[0] <= max_width:
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)
    return lines

class BookReader:
    def __init__(self, book_file):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Pixel Book Reader")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont(None, 24)  # Standard system font

        self.book_file = book_file
        self.lines = self.load_book(book_file)
        self.lines_per_page = 19
        self.pages = self.split_into_pages_wrapped(self.lines, self.font, (WIDTH - 200) // 2, 24, HEIGHT - 100, 100
        )

        self.chapters = self.find_chapters(self.lines)
        self.current_page = 0
        self.bookmark = None

        # Pixel-art background image
        self.book_bg = pygame.image.load("assets/GFX/UI/book_bg.png").convert_alpha() if os.path.exists("assets/GFX/UI/book_bg.png") else None

    def load_book(self, filename):
        with open(filename, "r", encoding="utf-8") as f:
            return [line.strip() for line in f.readlines()]

    def split_into_pages(self, lines, lines_per_page):
        return [lines[i:i+lines_per_page] for i in range(0, len(lines), lines_per_page)]

    def find_chapters(self, lines):
        chapters = {}
        for i, line in enumerate(lines):
            if line.lower().startswith("chapter"):
                chapter_num = line.split(" ")[-1]
                chapters[chapter_num] = i
        return chapters
    
    def draw_page(self):
        surface = pygame.Surface((WIDTH, HEIGHT))
        surface.fill((20, 20, 20))
        if self.book_bg:
            bg_scaled = pygame.transform.scale(self.book_bg, (WIDTH, HEIGHT))
            surface.blit(bg_scaled, (0, 0))

        if self.current_page < len(self.pages):
            # Wrap lines
            lines = self.pages[self.current_page]
            column_width = 380
            wrapped_lines = []
            for line in lines:
                wrapped_lines.extend(wrap_line(line, self.font, column_width))

            # Draw in two columns
            col1_x = 165
            col2_x = col1_x + column_width + 162
            y1 = 100
            y2 = 100
            halfway = len(wrapped_lines) // 2
            for i, line in enumerate(wrapped_lines):
                rendered_text = self.font.render(line, True, (0, 0, 0))
                if i < halfway:
                    surface.blit(rendered_text, (col1_x, y1))
                    y1 += 24
                else:
                    surface.blit(rendered_text, (col2_x, y2))
                    y2 += 24

        page_text = f"Page {self.current_page + 1}/{len(self.pages)}"
        page_surface = self.font.render(page_text, True, (200, 200, 0))
        surface.blit(page_surface, (WIDTH - 150, HEIGHT - 30))

        return surface


    def animate_page_turn(self, new_page_surface):
        old_page_surface = self.draw_page()
        for alpha in range(0, 256, 15):
            old_page_surface.set_alpha(255 - alpha)
            new_page_surface.set_alpha(alpha)
            self.screen.blit(old_page_surface, (0, 0))
            self.screen.blit(new_page_surface, (0, 0))
            pygame.display.flip()
            self.clock.tick(60)

    def jump_to_chapter(self, chapter_number):
        if chapter_number in self.chapters:
            line_index = self.chapters[chapter_number]
            new_page = line_index // self.lines_per_page
            self.animate_page_turn(self.draw_page_surface(new_page))
            self.current_page = new_page
        else:
            print("Chapter not found!")

    def split_into_pages_wrapped(self, lines, font, column_width, line_height, page_height, top_margin):
        pages = []
        current_page = []
        wrapped_line_count = 0  # Count of visible wrapped lines

        for line in lines:
            wrapped_lines = wrap_line(line, font, column_width)
            for wrapped_line in wrapped_lines:
                if wrapped_line_count >= self.lines_per_page:
                    pages.append(current_page)
                    current_page = []
                    wrapped_line_count = 0
                current_page.append(wrapped_line)
                wrapped_line_count += 1

        # Add the last page if there are leftovers
        if current_page:
            pages.append(current_page)

        return pages


    def jump_to_page(self, page_number):
        if 0 <= page_number < len(self.pages):
            self.animate_page_turn(self.draw_page_surface(page_number))
            self.current_page = page_number
        else:
            print("Invalid page number!")

    def draw_page_surface(self, page_number):
        # Helper to create a surface for a specific page
        original_page = self.current_page
        self.current_page = page_number
        surface = self.draw_page()
        self.current_page = original_page
        return surface

    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RIGHT:
                        if self.current_page < len(self.pages) - 1:
                            new_page_surface = self.draw_page_surface(self.current_page + 1)
                            self.animate_page_turn(new_page_surface)
                            self.current_page += 1
                    elif event.key == pygame.K_LEFT:
                        if self.current_page > 0:
                            new_page_surface = self.draw_page_surface(self.current_page - 1)
                            self.animate_page_turn(new_page_surface)
                            self.current_page -= 1
                    elif event.key == pygame.K_c:
                        chapter = input("Enter chapter number: ")
                        self.jump_to_chapter(chapter)
                    elif event.key == pygame.K_p:
                        page = int(input("Enter page number: ")) - 1
                        self.jump_to_page(page)
                    elif event.key == pygame.K_b:
                        self.bookmark = self.current_page
                        print("Bookmarked page:", self.current_page + 1)
                    elif event.key == pygame.K_r:
                        if self.bookmark is not None:
                            new_page_surface = self.draw_page_surface(self.bookmark)
                            self.animate_page_turn(new_page_surface)
                            self.current_page = self.bookmark
                            print("Jumped to bookmark page:", self.bookmark + 1)

            # Draw current page (no animation)
            page_surface = self.draw_page()
            self.screen.blit(page_surface, (0, 0))
            pygame.display.flip()
            self.clock.tick(60)

        pygame.quit()



reader = BookReader("assets/books/Pride and Prejudice.txt")
reader.run()

